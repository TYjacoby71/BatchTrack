# app/services/inventory_adjustment/_edit_logic.py

from flask_login import current_user
from app.models import db, InventoryItem
from ._core import process_inventory_adjustment

def update_inventory_item(item_id, form_data):
    """Handles the complex logic of updating an inventory item from a form."""
    try:
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, "Item not found."

        # --- Update Basic Fields ---
        item.name = form_data.get('name', item.name)
        # (Add other simple field updates here: category, low_stock_threshold, etc.)

        # --- Handle Quantity Update via Recount ---
        new_quantity_str = form_data.get('quantity')
        if new_quantity_str is not None:
            new_quantity = float(new_quantity_str)
            if abs(new_quantity - (item.quantity or 0.0)) > 0.001:
                success = process_inventory_adjustment(
                    item_id=item.id,
                    quantity=new_quantity,
                    change_type='recount',
                    notes=f"Quantity updated via edit form: {item.quantity} -> {new_quantity}",
                    created_by=current_user.id
                )
                if not success:
                    return False, "Error while updating quantity."

        # (Add other complex logic here like unit conversion, perishable status, etc.)

        db.session.commit()
        return True, "Inventory item updated successfully."

    except Exception as e:
        db.session.rollback()
        return False, f"An error occurred: {e}"