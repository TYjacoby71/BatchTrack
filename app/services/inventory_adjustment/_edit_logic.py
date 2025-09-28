from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory, IngredientCategory
from app.models.inventory_lot import InventoryLot
from app.models.unit import Unit
from app.services.unit_conversion import ConversionEngine
from flask import session
from app.services.density_assignment_service import DensityAssignmentService
from sqlalchemy import and_
import logging

logger = logging.getLogger(__name__)


def update_inventory_item(item_id: int, form_data: dict) -> tuple[bool, str]:
    """
    Update inventory item details.
    Handles name, cost, category, and other metadata changes.

    NOTE: Quantity changes are NOT handled here - use process_inventory_adjustment 
    with change_type='recount' for quantity updates.
    """
    try:
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, "Inventory item not found"

        # Disallow identity edits when globally managed
        is_global_locked = getattr(item, 'global_item_id', None) is not None

        if is_global_locked:
            # Prevent changes to name, category, density for globally-managed items (unit is user-editable)
            for forbidden_key in ['name', 'category_id', 'density', 'item_density']:
                if forbidden_key in form_data and str(form_data.get(forbidden_key)).strip() != str(getattr(item, 'name' if forbidden_key=='name' else forbidden_key, '')):
                    return False, "This item is managed by the global catalog. Identity fields cannot be edited."

        # Handle base unit change with conversion of existing inventory
        if 'unit' in form_data and form_data['unit'] and form_data['unit'] != item.unit:
            new_unit = form_data['unit']
            old_unit = item.unit

            # Determine convertibility
            try:
                # Probe convertibility with a value of 1.0
                ConversionEngine.convert_units(
                    amount=1.0,
                    from_unit=old_unit,
                    to_unit=new_unit,
                    ingredient_id=item.id,
                    density=item.density
                )
            except Exception as e:
                return False, f"Cannot change base unit from {old_unit} to {new_unit}: {str(e)}"

            # Convert item.quantity to new unit
            try:
                qconv = ConversionEngine.convert_units(
                    amount=float(item.quantity or 0.0),
                    from_unit=old_unit,
                    to_unit=new_unit,
                    ingredient_id=item.id,
                    density=item.density
                )
                item.quantity = qconv['converted_value']
            except Exception as e:
                return False, f"Error converting item quantity to {new_unit}: {str(e)}"

            # Convert each lot quantities and unit to the new unit
            lots = InventoryLot.query.filter_by(inventory_item_id=item.id).all()
            for lot in lots:
                try:
                    rem_conv = ConversionEngine.convert_units(
                        amount=float(lot.remaining_quantity or 0.0),
                        from_unit=lot.unit,
                        to_unit=new_unit,
                        ingredient_id=item.id,
                        density=item.density
                    )
                    orig_conv = ConversionEngine.convert_units(
                        amount=float(lot.original_quantity or 0.0),
                        from_unit=lot.unit,
                        to_unit=new_unit,
                        ingredient_id=item.id,
                        density=item.density
                    )
                    lot.remaining_quantity = rem_conv['converted_value']
                    lot.original_quantity = orig_conv['converted_value']
                    lot.unit = new_unit
                except Exception as e:
                    return False, f"Error converting lot #{lot.id} to {new_unit}: {str(e)}"

            # Persist the unit change on the item after converting all data
            item.unit = new_unit

        # Capacity fields (canonical only)
        if 'capacity' in form_data:
            try:
                cap_value = form_data.get('capacity')
                if cap_value not in [None, '', 'null']:
                    item.capacity = float(cap_value)
            except (ValueError, TypeError):
                return False, "Invalid capacity value"

        if 'capacity_unit' in form_data and form_data.get('capacity_unit'):
            item.capacity_unit = form_data.get('capacity_unit')

        # Container structured attributes (material/type/style)
        if item.type == 'container':
            if 'container_material' in form_data:
                item.container_material = (form_data.get('container_material') or '').strip() or None
            if 'container_type' in form_data:
                item.container_type = (form_data.get('container_type') or '').strip() or None
            if 'container_style' in form_data:
                item.container_style = (form_data.get('container_style') or '').strip() or None

        # Update basic item details (excluding quantity)
        if 'name' in form_data and not is_global_locked:
            item.name = form_data['name'].strip()

        if 'cost_per_unit' in form_data and form_data['cost_per_unit']:
            try:
                item.cost_per_unit = float(form_data['cost_per_unit'])
            except (ValueError, TypeError):
                return False, "Invalid cost per unit value"

        # Handle category selection and clearing
        if 'category_id' in form_data and not is_global_locked:
            raw_category = form_data.get('category_id')
            if raw_category in [None, '', 'null']:
                # No category selected: clear linkage and allow manual density
                item.category_id = None
            else:
                try:
                    category_id = int(raw_category)
                    item.category_id = category_id
                    # Apply chosen category default density if category exists
                    cat = db.session.get(IngredientCategory, category_id)
                    if cat and cat.default_density:
                        item.density = cat.default_density
                        try:
                            setattr(item, 'density_source', 'category_default')
                        except Exception:
                            pass
                except (ValueError, TypeError):
                    return False, "Invalid category ID"

        if 'low_stock_threshold' in form_data:
            try:
                threshold = form_data['low_stock_threshold']
                item.low_stock_threshold = float(threshold) if threshold else None
            except (ValueError, TypeError):
                return False, "Invalid low stock threshold"

        # Unit already handled above if present

        if 'is_perishable' in form_data:
            item.is_perishable = form_data['is_perishable'] in ['True', 'true', '1', 'on']

        if 'shelf_life_days' in form_data:
            try:
                shelf_life = form_data['shelf_life_days']
                item.shelf_life_days = int(shelf_life) if shelf_life else None
            except (ValueError, TypeError):
                return False, "Invalid shelf life days"

        # Handle density updates for ingredients and any item supporting density
        # Accept keys: 'density' or 'item_density' from forms
        if (('density' in form_data) or ('item_density' in form_data)):
            # If any category is selected (not Custom), ignore manual density edits
            try:
                if item.category_id:
                    form_data.pop('density', None)
                    form_data.pop('item_density', None)
                    try:
                        setattr(item, 'density_source', 'category_default')
                    except Exception:
                        pass
                    # Skip manual density handling since category selection governs density
                    pass
            except Exception:
                # Fall back to manual handling below if any error
                pass
            if is_global_locked:
                return False, "This item is managed by the global catalog. Density cannot be edited."
            density_value = form_data.get('density', form_data.get('item_density'))
            try:
                if density_value in [None, "", "null"]:
                    item.density = None
                else:
                    parsed = float(density_value)
                    if parsed <= 0:
                        return False, "Density must be greater than 0 g/mL"
                    item.density = parsed
                # Mark source as manual when explicitly set
                if 'density' in form_data or 'item_density' in form_data:
                    try:
                        setattr(item, 'density_source', 'manual')
                    except Exception:
                        pass
            except (ValueError, TypeError):
                return False, "Invalid density value; please provide a numeric g/mL value"

        db.session.commit()
        return True, f"Updated {item.name} successfully"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating inventory item {item_id}: {str(e)}")
        return False, f"Database error: {str(e)}"