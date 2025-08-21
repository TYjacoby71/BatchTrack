from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory, IngredientCategory
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

        if 'unit' in form_data:
            item.unit = form_data['unit']

        if 'is_perishable' in form_data:
            item.is_perishable = form_data['is_perishable'] in ['True', 'true', '1', 'on']

        if 'shelf_life_days' in form_data:
            try:
                shelf_life = form_data['shelf_life_days']
                item.shelf_life_days = int(shelf_life) if shelf_life else None
            except (ValueError, TypeError):
                return False, "Invalid shelf life days"

        db.session.commit()
        return True, f"Updated {item.name} successfully"

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating inventory item {item_id}: {str(e)}")
        return False, f"Database error: {str(e)}"