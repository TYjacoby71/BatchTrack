from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory, IngredientCategory
from app.models.inventory_lot import InventoryLot
from app.models.unit import Unit
from app.services.unit_conversion import ConversionEngine
from flask import session
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

        # Update basic item details (excluding quantity)
        if 'name' in form_data:
            item.name = form_data['name'].strip()

        if 'cost_per_unit' in form_data and form_data['cost_per_unit']:
            try:
                item.cost_per_unit = float(form_data['cost_per_unit'])
            except (ValueError, TypeError):
                return False, "Invalid cost per unit value"

        if 'category_id' in form_data and form_data['category_id']:
            try:
                item.category_id = int(form_data['category_id'])
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
        if 'density' in form_data or 'item_density' in form_data:
            density_value = form_data.get('density', form_data.get('item_density'))
            try:
                item.density = float(density_value) if density_value not in [None, "", "null"] else None
            except (ValueError, TypeError):
                return False, "Invalid density value; please provide a numeric g/mL value"

        db.session.commit()
        return True, f"Updated {item.name} successfully"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating inventory item {item_id}: {str(e)}")
        return False, f"Database error: {str(e)}"