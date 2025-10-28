"""
Creation logic handler - handles initial stock entries for new items.
This handler should work with the centralized quantity update system.
"""

import logging
from app.models import db, InventoryItem, IngredientCategory, Unit, UnifiedInventoryHistory, GlobalItem
from app.services.density_assignment_service import DensityAssignmentService
from ._fifo_ops import create_new_fifo_lot

logger = logging.getLogger(__name__)

def create_inventory_item(form_data, organization_id, created_by):
    """
    Create a new inventory item from form data.
    Returns (success, message, item_id)
    """
    try:
        logger.info(f"CREATE INVENTORY ITEM: Organization {organization_id}, User {created_by}")
        logger.info(f"Form data: {dict(form_data)}")

        # Extract and validate required fields
        name = form_data.get('name', '').strip()
        if not name:
            return False, "Item name is required", None

        # If provided, load global item for defaults
        global_item_id = form_data.get('global_item_id')
        global_item = None
        if global_item_id:
            try:
                global_item = db.session.get(GlobalItem, int(global_item_id))
            except Exception:
                global_item = None

        # Determine item type, preferring global item if provided
        item_type = form_data.get('type') or (global_item.item_type if global_item else 'ingredient')
        # Validate type against global item
        if global_item and item_type != global_item.item_type:
            return False, f"Selected global item type '{global_item.item_type}' does not match item type '{item_type}'.", None

        # Handle unit - prefer global item's default unit, then form input
        unit_input = None
        if global_item and global_item.default_unit:
            # Use global item's default unit directly
            unit_input = global_item.default_unit
        elif form_data.get('unit', '').strip():
            # Fall back to form input if no global item default
            unit_input = form_data.get('unit', '').strip()

        if unit_input:
            # Just use the unit name - don't try to create units here
            # The system should already have standard units available
            final_unit = unit_input
        else:
            # Default based on item type
            if item_type == 'container':
                final_unit = 'count'
            else:
                final_unit = 'gram'  # Default for ingredients

        # Handle base category selector and custom density (defer density application until after item exists)
        category_id = None
        raw_category_id = form_data.get('category_id')
        custom_density = form_data.get('density')
        if raw_category_id and raw_category_id != 'custom':
            # Legacy custom IngredientCategory by id
            try:
                category_id = int(raw_category_id)
            except Exception:
                category_id = None

        # Extract numeric fields with defaults
        cost_per_unit = 0.0
        try:
            cost_input = form_data.get('cost_per_unit')
            if cost_input:
                cost_per_unit = float(cost_input)
        except (ValueError, TypeError):
            pass

        shelf_life_days = None
        try:
            shelf_life_input = form_data.get('shelf_life_days')
            if shelf_life_input:
                shelf_life_days = int(shelf_life_input)
        except (ValueError, TypeError):
            pass

        # Extract initial quantity from form
        initial_quantity = 0.0
        try:
            quantity_input = form_data.get('quantity')
            if quantity_input:
                initial_quantity = float(quantity_input)
        except (ValueError, TypeError):
            pass

        # Determine if item is perishable
        is_perishable = bool(shelf_life_days) or form_data.get('is_perishable') == 'on'
        # Apply perishable defaults from global item if not explicitly set
        if global_item:
            if form_data.get('is_perishable') is None and global_item.default_is_perishable is not None:
                is_perishable = bool(global_item.default_is_perishable)
            if not shelf_life_days and global_item.recommended_shelf_life_days:
                shelf_life_days = int(global_item.recommended_shelf_life_days)

        # Create the new inventory item with quantity = 0
        # The initial stock will be added via process_inventory_adjustment
        new_item = InventoryItem(
            name=name,
            type=item_type,
            quantity=0.0,  # Start with 0, will be set by initial stock adjustment
            unit=final_unit,
            cost_per_unit=cost_per_unit,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            organization_id=organization_id,
            category_id=category_id,
            global_item_id=(global_item.id if global_item else None),
            ownership=('global' if global_item else 'org')
        )

        # Capacity fields (canonical only)
        try:
            raw_capacity = form_data.get('capacity')
            if raw_capacity not in [None, '', 'null']:
                new_item.capacity = float(raw_capacity)
        except (ValueError, TypeError):
            pass

        cap_unit = form_data.get('capacity_unit')
        if cap_unit:
            new_item.capacity_unit = cap_unit

        # Containers are always counted by "count"; ensure unit is correct
        if item_type == 'container':
            new_item.unit = 'count'

        # Container structured attributes (material/type/style)
        if item_type == 'container':
            try:
                mat = (form_data.get('container_material') or '').strip()
                ctype = (form_data.get('container_type') or '').strip()
                style = (form_data.get('container_style') or '').strip()
                color = (form_data.get('container_color') or '').strip()
                new_item.container_material = mat or None
                new_item.container_type = ctype or None
                new_item.container_style = style or None
                new_item.container_color = color or None
            except Exception:
                pass

        # Apply global item defaults after instance is created
        if global_item:
            # Density for ingredients
            if global_item.density is not None and item_type == 'ingredient':
                new_item.density = global_item.density
            # Capacity for containers/packaging (nullable by design)
            if global_item.capacity is not None:
                new_item.capacity = global_item.capacity
            if global_item.capacity_unit is not None:
                new_item.capacity_unit = global_item.capacity_unit
            # Container structured attributes defaults
            try:
                if item_type == 'container':
                    if getattr(global_item, 'container_material', None):
                        new_item.container_material = global_item.container_material
                    if getattr(global_item, 'container_type', None):
                        new_item.container_type = global_item.container_type
                    if getattr(global_item, 'container_style', None):
                        new_item.container_style = global_item.container_style
                    if getattr(global_item, 'container_color', None):
                        new_item.container_color = global_item.container_color
            except Exception:
                pass

        # Resolve category linkage and density precedence
        # 1) If a category ID was chosen, link and assign its default density
        if category_id:
            try:
                cat = db.session.get(IngredientCategory, int(category_id))
                if cat:
                    new_item.category_id = cat.id
                    # Assign category default density only for custom items
                    if not global_item:
                        DensityAssignmentService.assign_density_to_ingredient(
                            ingredient=new_item,
                            use_category_default=True,
                            category_name=cat.name
                        )
            except Exception:
                pass

        # 2) If a global item was selected, ensure category linkage to matching IngredientCategory by name
        if global_item and global_item.ingredient_category:
            try:
                cat = db.session.query(IngredientCategory).filter_by(name=global_item.ingredient_category.name, organization_id=organization_id).first()
                if cat:
                    new_item.category_id = cat.id
            except Exception:
                pass

        # 3) If no density provided and no global item and no ref category assignment, try auto-assign based on name/category
        if (not global_item) and (not custom_density) and not category_id:
            try:
                # Assign density via reference or category keyword
                DensityAssignmentService.auto_assign_density_on_creation(new_item)
                # If density came from a category default, also set category_id when possible
                match_item, match_type = DensityAssignmentService.find_best_match(new_item.name)
                inferred_category_name = None
                if match_item and match_type == 'category_keyword':
                    inferred_category_name = match_item.get('category')
                elif match_item and match_type in ['exact', 'alias', 'similarity']:
                    # Use the category tied to the matched reference item if available
                    inferred_category_name = match_item.get('category')

                if inferred_category_name:
                    try:
                        cat = db.session.query(IngredientCategory).filter_by(
                            name=inferred_category_name,
                            organization_id=organization_id
                        ).first()
                        if cat:
                            new_item.category_id = cat.id
                            # Ensure density aligns with category default when available
                            if cat.default_density and cat.default_density > 0:
                                new_item.density = cat.default_density
                                try:
                                    setattr(new_item, 'density_source', 'category_default')
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception:
                pass

        # 4) If user provided custom density, override
        if custom_density not in [None, '', 'null']:
            try:
                parsed = float(custom_density)
                if parsed > 0:
                    new_item.density = parsed
                    new_item.density_source = 'manual'
            except Exception:
                pass

        # Save the new item
        db.session.add(new_item)
        db.session.flush()  # Get the ID without committing

        logger.info(f"CREATED: New inventory item {new_item.id} - {new_item.name}")

        # Handle initial stock if quantity > 0
        if initial_quantity > 0:
            # Extract custom expiration data for initial stock
            custom_expiration_date = form_data.get('custom_expiration_date')
            custom_shelf_life_days = form_data.get('custom_shelf_life_days')

            # Use the local initial stock handler (no circular dependency)
            success, adjustment_message, quantity_delta = handle_initial_stock(
                item=new_item,
                quantity=initial_quantity,
                change_type='initial',
                notes='Initial inventory entry',
                created_by=created_by,
                custom_expiration_date=custom_expiration_date,
                custom_shelf_life_days=custom_shelf_life_days,
                unit=final_unit
            )

            if not success:
                db.session.rollback()
                return False, f"Item created but initial stock failed: {adjustment_message}", None

            # Apply the quantity delta to the item
            new_item.quantity = float(quantity_delta)

        # Commit the transaction
        db.session.commit()

        # Double-check the item was created
        created_item = InventoryItem.query.get(new_item.id)
        if not created_item:
            logger.error(f"Item {new_item.id} not found after creation")
            return False, "Item creation failed - not found after commit", None

        return True, f"Created {new_item.name}", new_item.id

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating inventory item: {str(e)}")
        return False, f"Failed to create inventory item: {str(e)}", None

def handle_initial_stock(item, quantity, change_type, notes=None, created_by=None, cost_override=None, custom_expiration_date=None, custom_shelf_life_days=None, **kwargs):
    """
    Handle the initial stock entry for a newly created item.
    This is called when an item gets its very first inventory.
    Works just like any other lot creation - can be 0 or any positive value.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"INITIAL_STOCK: Adding {quantity} to new item {item.id}")

        unit = kwargs.get('unit') or item.unit or 'count'
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        # Create the initial FIFO entry - works for any quantity including 0
        success, message, lot_id = create_new_fifo_lot(
            item_id=item.id,
            quantity=quantity,
            change_type='initial_stock',
            unit=unit,
            notes=notes or "Initial stock entry",
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            custom_shelf_life_days=custom_shelf_life_days
        )

        if not success:
            return False, f"Failed to create initial stock entry: {message}", 0

        # The create_new_fifo_lot already created the history record
        # No need to create a duplicate here

        # Return delta for core to apply - works for 0 quantity too
        quantity_delta = float(quantity)
        logger.info(f"INITIAL_STOCK SUCCESS: Will set item {item.id} quantity to {quantity}")

        if quantity == 0:
            return True, f"Initial stock entry created with 0 {unit}", quantity_delta
        else:
            return True, f"Initial stock of {quantity} {unit} added", quantity_delta

    except Exception as e:
        logger.error(f"Error in initial stock operation: {str(e)}")
        return False, f"Initial stock failed: {str(e)}", 0