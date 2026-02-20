"""Inventory creation logic handlers.

Synopsis:
Create initial inventory items and seed starting stock entries.

Glossary:
- Initial stock: First inventory quantity recorded for an item.
- Creation logic: Validation and setup for new inventory items.
"""

import logging
from datetime import timezone  # Import timezone for timezone-aware datetime objects

from sqlalchemy import func

from app.models import GlobalItem, IngredientCategory, InventoryItem, Organization, db
from app.services.container_name_builder import build_container_name
from app.services.density_assignment_service import DensityAssignmentService
from app.services.inventory_tracking_policy import (
    org_allows_inventory_quantity_tracking,
)
from app.services.quantity_base import sync_item_quantity_from_base, to_base_quantity

from ._fifo_ops import create_new_fifo_lot, get_or_create_infinite_anchor_lot

logger = logging.getLogger(__name__)


# --- Parse boolean flag ---
# Purpose: Normalize form checkbox-like values into boolean/None.
# Inputs: Raw value from form payload.
# Outputs: True/False for recognized flags, otherwise None.
def _parse_bool_flag(raw_value):
    if raw_value is None:
        return None
    if isinstance(raw_value, bool):
        return raw_value
    text = str(raw_value).strip().lower()
    if text in {"1", "true", "on", "yes"}:
        return True
    if text in {"0", "false", "off", "no"}:
        return False
    return None


# --- Resolve unit cost ---
# Purpose: Normalize form inputs into per-unit cost.
# Inputs: Form payload mapping and parsed initial quantity value.
# Outputs: Tuple of (cost_per_unit: float, error_message: str|None).
def _resolve_cost_per_unit(form_data, initial_quantity):
    """Convert form inputs into a per-unit cost."""
    try:
        quantity_value = float(initial_quantity)
    except (ValueError, TypeError):
        quantity_value = 0.0

    cost_entry_type = (form_data.get("cost_entry_type") or "per_unit").strip().lower()
    if cost_entry_type not in {"per_unit", "total"}:
        cost_entry_type = "per_unit"

    raw_cost_value = None
    try:
        cost_input = form_data.get("cost_per_unit")
        if cost_input not in (None, "", "null"):
            raw_cost_value = float(cost_input)
    except (ValueError, TypeError):
        raw_cost_value = None

    if raw_cost_value is None:
        return 0.0, None

    if cost_entry_type == "total":
        if quantity_value <= 0:
            return (
                0.0,
                "Total cost entry requires a positive quantity when using total cost mode.",
            )
        return raw_cost_value / quantity_value, None

    return raw_cost_value, None


# --- Normalize container field ---
# Purpose: Canonicalize optional container attribute strings for matching.
# Inputs: Raw container attribute value.
# Outputs: Lowercased string value or None when empty.
def _normalize_container_field(value):
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


# --- Apply normalized string filter ---
# Purpose: Apply null-safe case-insensitive filtering for container attributes.
# Inputs: SQLAlchemy query, model column, and raw value to match.
# Outputs: Updated SQLAlchemy query with normalized attribute predicate.
def _apply_string_match(query, column, value):
    normalized = _normalize_container_field(value)
    if normalized is None:
        return query.filter(column.is_(None))
    return query.filter(func.lower(column) == normalized)


# --- Find matching container ---
# Purpose: Identify an existing container with matching attributes.
# Inputs: Candidate InventoryItem used for same-shape lookup.
# Outputs: Matching InventoryItem or None when no match is found.
def _find_matching_container(candidate: InventoryItem | None):
    """Return an existing container with matching attributes (same org)."""
    if not candidate or candidate.type != "container":
        return None

    query = InventoryItem.query.filter(
        InventoryItem.organization_id == candidate.organization_id,
        InventoryItem.type == "container",
    )

    query = _apply_string_match(
        query, InventoryItem.container_material, candidate.container_material
    )
    query = _apply_string_match(
        query, InventoryItem.container_type, candidate.container_type
    )
    query = _apply_string_match(
        query, InventoryItem.container_style, candidate.container_style
    )
    query = _apply_string_match(
        query, InventoryItem.container_color, candidate.container_color
    )
    query = _apply_string_match(
        query, InventoryItem.capacity_unit, candidate.capacity_unit
    )

    if candidate.capacity is None:
        query = query.filter(InventoryItem.capacity.is_(None))
    else:
        query = query.filter(InventoryItem.capacity == candidate.capacity)

    return query.first()


# --- Create inventory item ---
# Purpose: Create inventory item with initial metadata.
# Inputs: Form payload, organization id, creator id, and commit mode flag.
# Outputs: Tuple of (success, message, created_item_id).
def create_inventory_item(
    form_data, organization_id, created_by, auto_commit: bool = True
):
    """
    Create a new inventory item from form data.
    Returns (success, message, item_id)
    """
    try:
        logger.info(
            f"CREATE INVENTORY ITEM: Organization {organization_id}, User {created_by}"
        )
        logger.info(f"Form data: {dict(form_data)}")

        # Extract and validate required fields
        name = (form_data.get("name") or "").strip()

        # If provided, load global item for defaults
        global_item_id = form_data.get("global_item_id")
        global_item = None
        if global_item_id:
            try:
                global_item = db.session.get(GlobalItem, int(global_item_id))
            except Exception:
                global_item = None

        # Determine item type, preferring global item if provided
        item_type = form_data.get("type") or (
            global_item.item_type if global_item else "ingredient"
        )
        # Validate type against global item
        if global_item and item_type != global_item.item_type:
            return (
                False,
                f"Selected global item type '{global_item.item_type}' does not match item type '{item_type}'.",
                None,
            )

        def _container_attr(key: str):
            value = form_data.get(key)
            if isinstance(value, str):
                value = value.strip()
            if value not in (None, "", "null"):
                return value
            if global_item:
                return getattr(global_item, key, None)
            return None

        if item_type == "container":
            name = build_container_name(
                style=_container_attr("container_style"),
                material=_container_attr("container_material"),
                container_type=_container_attr("container_type"),
                color=_container_attr("container_color"),
                capacity=_container_attr("capacity"),
                capacity_unit=_container_attr("capacity_unit"),
            )

        if not name:
            return False, "Item name is required", None

        # Handle unit - prefer user's form selection over global item defaults
        unit_input = None
        if form_data.get("unit", "").strip():
            # User explicitly selected a unit in the form - this takes priority
            unit_input = form_data.get("unit", "").strip()
        elif global_item and global_item.default_unit:
            # Fall back to global item's default unit if no form input
            unit_input = global_item.default_unit

        if unit_input:
            # Just use the unit name - don't try to create units here
            # The system should already have standard units available
            final_unit = unit_input
        else:
            # Default based on item type
            if item_type == "container":
                final_unit = "count"
            else:
                final_unit = "gram"  # Default for ingredients

        # Handle base category selector and custom density (defer density application until after item exists)
        category_id = None
        raw_category_id = form_data.get("category_id")
        custom_density = form_data.get("density")
        if raw_category_id and raw_category_id != "custom":
            # Legacy custom IngredientCategory by id
            try:
                category_id = int(raw_category_id)
            except Exception:
                category_id = None

        # Extract numeric fields with defaults
        shelf_life_days = None
        try:
            shelf_life_input = form_data.get("shelf_life_days")
            if shelf_life_input:
                shelf_life_days = int(shelf_life_input)
        except (ValueError, TypeError):
            pass

        # Extract initial quantity from form
        initial_quantity = 0.0
        try:
            quantity_input = form_data.get("quantity")
            if quantity_input:
                initial_quantity = float(quantity_input)
        except (ValueError, TypeError):
            pass

        organization = (
            db.session.get(Organization, organization_id) if organization_id else None
        )
        org_tracks_quantities = org_allows_inventory_quantity_tracking(
            organization=organization
        )
        if not org_tracks_quantities:
            # Quantity-based stock entry is tier-locked; create item in infinite mode.
            initial_quantity = 0.0

        cost_per_unit, cost_error = _resolve_cost_per_unit(form_data, initial_quantity)
        if cost_error and not org_tracks_quantities:
            # In forced-infinite mode there is no opening quantity, so treat a submitted
            # "total" cost value as per-unit instead of failing creation.
            try:
                raw_cost_value = form_data.get("cost_per_unit")
                cost_per_unit = (
                    float(raw_cost_value)
                    if raw_cost_value not in (None, "", "null")
                    else 0.0
                )
                cost_error = None
            except (ValueError, TypeError):
                pass
        if cost_error:
            return False, cost_error, None

        # Determine if item is perishable - user input takes priority
        is_perishable = form_data.get("is_perishable") == "on"

        # If no explicit user input and global item has defaults, use them as fallback
        # This handles the case where form is pre-populated but user doesn't change it
        if (
            global_item
            and global_item.default_is_perishable
            and form_data.get("is_perishable") is None
        ):
            is_perishable = True

        # Use recommended shelf life from global item if none provided by user
        if (
            not shelf_life_days
            and global_item
            and global_item.recommended_shelf_life_days
        ):
            shelf_life_days = int(global_item.recommended_shelf_life_days)

        # Final validation: if shelf_life_days is provided, item must be perishable
        if shelf_life_days and not is_perishable:
            is_perishable = True

        requested_is_tracked = _parse_bool_flag(form_data.get("is_tracked"))
        if requested_is_tracked is None:
            effective_is_tracked = bool(org_tracks_quantities)
        else:
            # Tier-level policy can only further restrict tracking, never expand it.
            effective_is_tracked = bool(requested_is_tracked and org_tracks_quantities)
        if not effective_is_tracked:
            initial_quantity = 0.0

        # Create the new inventory item with quantity = 0
        # The initial stock will be added via process_inventory_adjustment
        new_item = InventoryItem(
            name=name,
            type=item_type,
            quantity=0.0,  # Start with 0, will be set by initial stock adjustment
            unit=final_unit,
            cost_per_unit=cost_per_unit,
            is_tracked=effective_is_tracked,
            is_perishable=is_perishable,
            shelf_life_days=shelf_life_days,
            organization_id=organization_id,
            category_id=category_id,
            global_item_id=(global_item.id if global_item else None),
            ownership=("global" if global_item else "org"),
        )

        # Capacity fields (canonical only)
        try:
            raw_capacity = form_data.get("capacity")
            if raw_capacity not in [None, "", "null"]:
                new_item.capacity = float(raw_capacity)
        except (ValueError, TypeError):
            pass

        cap_unit = form_data.get("capacity_unit")
        if cap_unit:
            new_item.capacity_unit = cap_unit

        # Containers are always counted by "count"; ensure unit is correct
        if item_type == "container":
            new_item.unit = "count"

        # Container structured attributes (material/type/style)
        if item_type == "container":
            try:
                mat = (form_data.get("container_material") or "").strip()
                ctype = (form_data.get("container_type") or "").strip()
                style = (form_data.get("container_style") or "").strip()
                color = (form_data.get("container_color") or "").strip()
                new_item.container_material = mat or None
                new_item.container_type = ctype or None
                new_item.container_style = style or None
                new_item.container_color = color or None
            except Exception:
                pass

        # Apply global item defaults after instance is created
        if global_item:
            # Density for ingredients
            if global_item.density is not None and item_type == "ingredient":
                new_item.density = global_item.density
            # Capacity for containers/packaging (nullable by design)
            if global_item.capacity is not None:
                new_item.capacity = global_item.capacity
            if global_item.capacity_unit is not None:
                new_item.capacity_unit = global_item.capacity_unit
            # Container structured attributes defaults
            try:
                if item_type == "container":
                    if getattr(global_item, "container_material", None):
                        new_item.container_material = global_item.container_material
                    if getattr(global_item, "container_type", None):
                        new_item.container_type = global_item.container_type
                    if getattr(global_item, "container_style", None):
                        new_item.container_style = global_item.container_style
                    if getattr(global_item, "container_color", None):
                        new_item.container_color = global_item.container_color
            except Exception:
                pass

            # Ingredient metadata defaults
            if item_type == "ingredient":
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
                            category_name=cat.name,
                        )
            except Exception:
                pass

        # 2) If a global item was selected, ensure category linkage to matching IngredientCategory by name
        if global_item and global_item.ingredient_category:
            try:
                cat = (
                    db.session.query(IngredientCategory)
                    .filter_by(
                        name=global_item.ingredient_category.name,
                        organization_id=organization_id,
                    )
                    .first()
                )
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
                match_item, match_type = DensityAssignmentService.find_best_match(
                    new_item.name
                )
                inferred_category_name = None
                if match_item and match_type == "category_keyword":
                    inferred_category_name = match_item.get("category")
                elif match_item and match_type in ["exact", "alias", "similarity"]:
                    # Use the category tied to the matched reference item if available
                    inferred_category_name = match_item.get("category")

                if inferred_category_name:
                    try:
                        cat = (
                            db.session.query(IngredientCategory)
                            .filter_by(
                                name=inferred_category_name,
                                organization_id=organization_id,
                            )
                            .first()
                        )
                        if cat:
                            new_item.category_id = cat.id
                            # Ensure density aligns with category default when available
                            if cat.default_density and cat.default_density > 0:
                                new_item.density = cat.default_density
                                try:
                                    setattr(
                                        new_item, "density_source", "category_default"
                                    )
                                except Exception:
                                    pass
                    except Exception:
                        pass
            except Exception:
                pass

        # 4) If user provided custom density, override
        if custom_density not in [None, "", "null"]:
            try:
                parsed = float(custom_density)
                if parsed > 0:
                    new_item.density = parsed
                    new_item.density_source = "manual"
            except Exception:
                pass

        # Before saving containers, reuse an existing match if attributes align
        if item_type == "container":
            existing_container = _find_matching_container(new_item)
            if existing_container:
                existing_id = existing_container.id
                existing_name = existing_container.name
                if existing_container.is_archived:
                    existing_container.is_archived = False
                db.session.commit()
                logger.info(
                    f"Matched existing container {existing_name} (ID: {existing_id}). Reusing record."
                )
                return True, f"Matched existing container {existing_name}", existing_id

        # Save the new item
        db.session.add(new_item)
        db.session.flush()  # Get the ID without committing

        logger.info(f"CREATED: New inventory item {new_item.id} - {new_item.name}")

        if not new_item.is_tracked:
            anchor_ok, anchor_message, _anchor_lot = get_or_create_infinite_anchor_lot(
                item_id=new_item.id,
                created_by=created_by,
            )
            if not anchor_ok:
                db.session.rollback()
                return (
                    False,
                    f"Item created but infinite anchor setup failed: {anchor_message}",
                    None,
                )

        # Handle initial stock if quantity > 0
        if initial_quantity > 0:
            # Extract custom expiration date for initial stock (date only, no custom shelf life)
            custom_expiration_date = form_data.get("custom_expiration_date")

            # Convert custom_expiration_date to proper format if provided
            if custom_expiration_date:
                try:
                    from datetime import datetime

                    if isinstance(custom_expiration_date, str):
                        # Parse string date and make it timezone-aware UTC
                        parsed_date = datetime.fromisoformat(
                            custom_expiration_date.replace("Z", "+00:00")
                        )
                        if parsed_date.tzinfo is None:
                            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                        custom_expiration_date = parsed_date
                except Exception:
                    custom_expiration_date = None

            # Use the local initial stock handler (no circular dependency)
            success, adjustment_message, quantity_delta, quantity_delta_base = (
                handle_initial_stock(
                    item=new_item,
                    quantity=initial_quantity,
                    change_type="initial",
                    notes="Initial inventory entry",
                    created_by=created_by,
                    custom_expiration_date=custom_expiration_date,
                    unit=final_unit,
                )
            )

            if not success:
                db.session.rollback()
                return (
                    False,
                    f"Item created but initial stock failed: {adjustment_message}",
                    None,
                )

            # Apply the quantity delta to the item
            new_item.quantity_base = int(quantity_delta_base)
            sync_item_quantity_from_base(new_item)

        # Commit or defer the transaction
        if auto_commit:
            db.session.commit()
        else:
            db.session.flush()

        # Double-check the item was created
        created_item = db.session.get(InventoryItem, new_item.id)
        if not created_item:
            logger.error(f"Item {new_item.id} not found after creation")
            return False, "Item creation failed - not found after commit", None

        try:
            from ..analytics_tracking_service import AnalyticsTrackingService

            creation_source = "global" if global_item else "custom"
            AnalyticsTrackingService.emit(
                event_name="inventory_item_created",
                properties={
                    "item_type": created_item.type,
                    "unit": created_item.unit,
                    "creation_source": creation_source,
                    "global_item_id": (
                        int(created_item.global_item_id)
                        if created_item.global_item_id
                        else None
                    ),
                    "is_tracked": bool(created_item.is_tracked),
                    "initial_quantity": float(initial_quantity or 0.0),
                },
                organization_id=created_item.organization_id,
                user_id=created_by,
                entity_type="inventory_item",
                entity_id=created_item.id,
                auto_commit=auto_commit,
            )
            source_event_name = (
                "inventory_item_global_created"
                if creation_source == "global"
                else "inventory_item_custom_created"
            )
            AnalyticsTrackingService.emit(
                event_name=source_event_name,
                properties={
                    "item_type": created_item.type,
                    "unit": created_item.unit,
                    "creation_source": creation_source,
                    "global_item_id": (
                        int(created_item.global_item_id)
                        if created_item.global_item_id
                        else None
                    ),
                    "is_tracked": bool(created_item.is_tracked),
                    "initial_quantity": float(initial_quantity or 0.0),
                },
                organization_id=created_item.organization_id,
                user_id=created_by,
                entity_type="inventory_item",
                entity_id=created_item.id,
                auto_commit=auto_commit,
            )
        except Exception:
            pass

        return True, f"Created {new_item.name}", new_item.id

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating inventory item: {str(e)}")
        return False, f"Failed to create inventory item: {str(e)}", None


# --- Initial stock ---
# Purpose: Handle initial stock entries for new items.
# Inputs: Item context, initial quantity/change metadata, and optional expiration fields.
# Outputs: Tuple of (success, message, quantity_delta, quantity_delta_base).
def handle_initial_stock(
    item,
    quantity,
    change_type,
    notes=None,
    created_by=None,
    cost_override=None,
    custom_expiration_date=None,
    **kwargs,
):
    """
    Handle the initial stock entry for a newly created item.
    This is called when an item gets its very first inventory.
    Works just like any other lot creation - can be 0 or any positive value.
    Returns (success, message, quantity_delta) - does NOT modify item.quantity
    """
    try:
        logger.info(f"INITIAL_STOCK: Adding {quantity} to new item {item.id}")

        unit = kwargs.get("unit") or item.unit or "count"
        final_cost = cost_override if cost_override is not None else item.cost_per_unit

        quantity_base = to_base_quantity(
            amount=quantity,
            unit_name=unit,
            ingredient_id=item.id,
            density=item.density,
        )

        # Create the initial FIFO entry - works for any quantity including 0
        # The custom_shelf_life_days parameter is removed as per the requirement.
        success, message, lot_id = create_new_fifo_lot(
            item_id=item.id,
            quantity=quantity,
            quantity_base=quantity_base,
            change_type="initial_stock",
            unit=unit,
            notes=notes or "Initial stock entry",
            cost_per_unit=final_cost,
            created_by=created_by,
            custom_expiration_date=custom_expiration_date,
            # custom_shelf_life_days removed here
        )

        if not success:
            return False, f"Failed to create initial stock entry: {message}", 0, 0

        # The create_new_fifo_lot already created the history record
        # No need to create a duplicate here

        # Return delta for core to apply - works for 0 quantity too
        quantity_delta = float(quantity)
        quantity_delta_base = int(quantity_base)
        logger.info(
            f"INITIAL_STOCK SUCCESS: Will set item {item.id} quantity to {quantity}"
        )

        if quantity == 0:
            return (
                True,
                f"Initial stock entry created with 0 {unit}",
                quantity_delta,
                quantity_delta_base,
            )
        else:
            return (
                True,
                f"Initial stock of {quantity} {unit} added",
                quantity_delta,
                quantity_delta_base,
            )

    except Exception as e:
        logger.error(f"Error in initial stock operation: {str(e)}")
        return False, f"Initial stock failed: {str(e)}", 0, 0
