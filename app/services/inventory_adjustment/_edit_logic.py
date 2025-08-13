# app/services/inventory_adjustment/_edit_logic.py

import logging
from flask_login import current_user
from app.models import db, InventoryItem, Category
from ._core import process_inventory_adjustment
from app.services.unit_conversion import ConversionEngine

logger = logging.getLogger(__name__)

def update_inventory_item(item_id, form_data):
    """Handles the complex logic of updating an inventory item from a form."""
    try:
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, "Item not found."

        # --- Update Basic Fields ---
        item.name = form_data.get('name', item.name)
        item.low_stock_threshold = form_data.get('low_stock_threshold', item.low_stock_threshold)
        item.notes = form_data.get('notes', item.notes)
        
        # Handle category update
        category_id = form_data.get('category_id')
        if category_id:
            category = db.session.get(Category, category_id)
            if category and category.organization_id == current_user.organization_id:
                item.category_id = category.id
        
        # Handle cost per unit
        cost_str = form_data.get('cost_per_unit')
        if cost_str is not None:
            try:
                item.cost_per_unit = ConversionEngine.round_value(float(cost_str), 3)
            except (ValueError, TypeError):
                logger.warning(f"Invalid cost_per_unit value: {cost_str}")
        
        # Handle perishable settings
        is_perishable = form_data.get('is_perishable')
        if is_perishable is not None:
            item.is_perishable = bool(is_perishable)
            
        shelf_life_str = form_data.get('shelf_life_days')
        if shelf_life_str is not None:
            try:
                item.shelf_life_days = int(shelf_life_str) if shelf_life_str else None
            except (ValueError, TypeError):
                logger.warning(f"Invalid shelf_life_days value: {shelf_life_str}")
        
        # Handle density for unit conversions
        density_str = form_data.get('density')
        if density_str is not None:
            try:
                item.density = ConversionEngine.round_value(float(density_str), 3) if density_str else None
            except (ValueError, TypeError):
                logger.warning(f"Invalid density value: {density_str}")

        # --- Handle Quantity Update via Recount ---
        new_quantity_str = form_data.get('quantity')
        if new_quantity_str is not None:
            try:
                new_quantity = ConversionEngine.round_value(float(new_quantity_str), 3)
                current_quantity = ConversionEngine.round_value(item.quantity or 0.0, 3)
                
                if abs(new_quantity - current_quantity) > 0.001:
                    success = process_inventory_adjustment(
                        item_id=item.id,
                        quantity=new_quantity,
                        change_type='recount',
                        unit=item.unit,
                        notes=f"Quantity updated via edit form: {current_quantity} -> {new_quantity}",
                        created_by=current_user.id
                    )
                    if not success:
                        return False, "Error while updating quantity."
            except (ValueError, TypeError):
                return False, f"Invalid quantity value: {new_quantity_str}"
        
        # --- Handle Unit Updates ---
        new_unit = form_data.get('unit')
        if new_unit and new_unit != item.unit:
            # Unit changes require careful validation
            from app.models import Unit
            unit_obj = db.session.query(Unit).filter_by(name=new_unit).first()
            if unit_obj:
                item.unit = new_unit
            else:
                logger.warning(f"Invalid unit specified: {new_unit}")

        db.session.commit()
        return True, "Inventory item updated successfully."

    except Exception as e:
        db.session.rollback()
        return False, f"An error occurred: {e}"