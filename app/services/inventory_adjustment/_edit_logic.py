from flask import session
from flask_login import current_user
from sqlalchemy import and_
import logging
import json

from app.models import db, InventoryItem, IngredientCategory
from app.models.inventory_lot import InventoryLot
from app.models.unit import Unit
from app.services.container_name_builder import build_container_name
from app.services.density_assignment_service import DensityAssignmentService
from app.services.unit_conversion import ConversionEngine
from app.services.quantity_base import (
    to_base_quantity,
    from_base_quantity,
    sync_item_quantity_from_base,
    sync_lot_quantities_from_base,
)

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

        # Disallow identity edits when globally managed (ownership != 'org')
        is_global_locked = (
            getattr(item, 'global_item_id', None) is not None
            and getattr(item, 'ownership', None) != 'org'
        )

        if is_global_locked:
            # Prevent changes to name, category, density for globally-managed items (unit is user-editable)
            for forbidden_key in ['name', 'category_id', 'density', 'item_density']:
                if forbidden_key in form_data and str(form_data.get(forbidden_key)).strip() != str(getattr(item, 'name' if forbidden_key=='name' else forbidden_key, '')):
                    return False, "This item is managed by the global catalog. Identity fields cannot be edited."

        # Handle base unit change with conversion of existing inventory
        if 'unit' in form_data and form_data['unit'] and form_data['unit'] != item.unit:
            new_unit = form_data['unit']
            old_unit = item.unit
            conversion_precision = None

            # Determine convertibility
            try:
                # Probe convertibility with a value of 1.0
                probe = ConversionEngine.convert_units(
                    amount=1.0,
                    from_unit=old_unit,
                    to_unit=new_unit,
                    ingredient_id=item.id,
                    density=item.density,
                    rounding_decimals=conversion_precision
                )
            except Exception as e:
                db.session.rollback()
                return False, f"Cannot change base unit from {old_unit} to {new_unit}: {str(e)}"

            if not probe or not probe.get('success'):
                db.session.rollback()
                err_msg = None
                if isinstance(probe, dict):
                    err_msg = probe.get('error_data', {}).get('message')
                return False, f"Cannot change base unit from {old_unit} to {new_unit}: {err_msg or 'Invalid conversion'}"

            # Convert each lot quantities and unit to the new unit (base units)
            lots = InventoryLot.query.filter_by(inventory_item_id=item.id).all()
            total_remaining_base = None
            for lot in lots:
                try:
                    rem_current = from_base_quantity(
                        base_amount=getattr(lot, "remaining_quantity_base", 0),
                        unit_name=old_unit,
                        ingredient_id=item.id,
                        density=item.density,
                        display_decimals=12,
                    )
                    orig_current = from_base_quantity(
                        base_amount=getattr(lot, "original_quantity_base", 0),
                        unit_name=old_unit,
                        ingredient_id=item.id,
                        density=item.density,
                        display_decimals=12,
                    )
                    rem_conv = ConversionEngine.convert_units(
                        amount=float(rem_current),
                        from_unit=old_unit,
                        to_unit=new_unit,
                        ingredient_id=item.id,
                        density=item.density,
                        rounding_decimals=conversion_precision
                    )
                    orig_conv = ConversionEngine.convert_units(
                        amount=float(orig_current),
                        from_unit=old_unit,
                        to_unit=new_unit,
                        ingredient_id=item.id,
                        density=item.density,
                        rounding_decimals=conversion_precision
                    )
                    if not rem_conv or not rem_conv.get('success') or rem_conv.get('converted_value') is None:
                        db.session.rollback()
                        return False, f"Error converting lot #{lot.id} remaining quantity to {new_unit}"
                    if not orig_conv or not orig_conv.get('success') or orig_conv.get('converted_value') is None:
                        db.session.rollback()
                        return False, f"Error converting lot #{lot.id} original quantity to {new_unit}"
                    lot.remaining_quantity_base = to_base_quantity(
                        amount=rem_conv['converted_value'],
                        unit_name=new_unit,
                        ingredient_id=item.id,
                        density=item.density,
                    )
                    lot.original_quantity_base = to_base_quantity(
                        amount=orig_conv['converted_value'],
                        unit_name=new_unit,
                        ingredient_id=item.id,
                        density=item.density,
                    )
                    lot.unit = new_unit
                    sync_lot_quantities_from_base(lot, item)
                    if total_remaining_base is None:
                        total_remaining_base = 0
                    total_remaining_base += int(lot.remaining_quantity_base or 0)
                except Exception as e:
                    db.session.rollback()
                    return False, f"Error converting lot #{lot.id} to {new_unit}: {str(e)}"

            # Convert item.quantity to new unit; if lots exist, use their total to stay in sync
            if total_remaining_base is None:
                try:
                    current_quantity = from_base_quantity(
                        base_amount=getattr(item, "quantity_base", 0),
                        unit_name=old_unit,
                        ingredient_id=item.id,
                        density=item.density,
                        display_decimals=12,
                    )
                    qconv = ConversionEngine.convert_units(
                        amount=float(current_quantity),
                        from_unit=old_unit,
                        to_unit=new_unit,
                        ingredient_id=item.id,
                        density=item.density,
                        rounding_decimals=conversion_precision
                    )
                    if not qconv or not qconv.get('success') or qconv.get('converted_value') is None:
                        db.session.rollback()
                        return False, f"Error converting item quantity to {new_unit}"
                    item.quantity_base = to_base_quantity(
                        amount=qconv['converted_value'],
                        unit_name=new_unit,
                        ingredient_id=item.id,
                        density=item.density,
                    )
                except Exception as e:
                    db.session.rollback()
                    return False, f"Error converting item quantity to {new_unit}: {str(e)}"
            else:
                item.quantity_base = int(total_remaining_base)

            # Persist the unit change on the item after converting all data
            item.unit = new_unit
            sync_item_quantity_from_base(item)

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
            if 'container_color' in form_data:
                item.container_color = (form_data.get('container_color') or '').strip() or None

        # Update basic item details (excluding quantity)
        if not is_global_locked:
            raw_name = form_data.get('name') if 'name' in form_data else None
            cleaned_name = raw_name.strip() if isinstance(raw_name, str) else (str(raw_name).strip() if raw_name else '')
            if cleaned_name:
                item.name = cleaned_name
            elif item.type == 'container':
                auto_name = build_container_name(
                    style=item.container_style,
                    material=item.container_material,
                    container_type=item.container_type,
                    color=item.container_color,
                    capacity=item.capacity,
                    capacity_unit=item.capacity_unit,
                )
                if auto_name:
                    item.name = auto_name

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
                old_shelf_life = item.shelf_life_days
                new_shelf_life = int(shelf_life) if shelf_life else None
                
                # Update the item's shelf life (affects future lots only)
                item.shelf_life_days = new_shelf_life
                
                # Note: Existing lots keep their original shelf_life_days and expiration_date
                # This is intentional - lots are immutable once created
                if old_shelf_life != new_shelf_life:
                    logger.info(f"Updated shelf life for item {item_id} from {old_shelf_life} to {new_shelf_life} days. Existing lots unchanged.")
                    
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

        if item.type == 'ingredient':
            converters = {
                'shelf_life_months': int,
            }

            for field_name, converter in converters.items():
                if field_name in form_data:
                    raw_value = form_data.get(field_name)
                    try:
                        if raw_value in (None, '', 'null'):
                            parsed = None
                        else:
                            parsed = converter(raw_value)
                        setattr(item, field_name, parsed)
                    except (ValueError, TypeError):
                        return False, f"Invalid numeric value for {field_name.replace('_', ' ')}"

            # Global-library attributes (soap/brewing/certs/INCI/CAS/etc) are not stored on InventoryItem.

        db.session.commit()
        return True, f"Updated {item.name} successfully"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating inventory item {item_id}: {str(e)}")
        return False, f"Database error: {str(e)}"