from flask_login import current_user
from app.models import db, InventoryItem, InventoryHistory, IngredientCategory
from flask import session
from sqlalchemy import and_
import logging
from ._core import process_inventory_adjustment

logger = logging.getLogger(__name__)


def update_inventory_item(item_id, form_data):
    """Handle all inventory item updates through the canonical service"""
    try:
        item = InventoryItem.query.get_or_404(item_id)

        # Handle unit changes with conversion confirmation
        if item.type != 'container':
            new_unit = form_data.get('unit')
            if new_unit != item.unit:
                history_count = InventoryHistory.query.filter_by(inventory_item_id=item_id).count()
                if history_count > 0:
                    confirm_unit_change = form_data.get('confirm_unit_change') == 'true'
                    convert_inventory = form_data.get('convert_inventory') == 'true'

                    if not confirm_unit_change:
                        session['pending_unit_change'] = {
                            'item_id': item_id,
                            'old_unit': item.unit,
                            'new_unit': new_unit,
                            'current_quantity': item.quantity
                        }
                        return False, f'Unit change requires confirmation. Item has {history_count} transaction history entries.'

                    if convert_inventory and item.quantity > 0:
                        try:
                            from app.services.unit_conversion import convert_unit
                            converted_quantity = convert_unit(item.quantity, item.unit, new_unit, item.density)
                            item.quantity = converted_quantity

                            history = InventoryHistory(
                                inventory_item_id=item.id,
                                change_type='unit_conversion',
                                quantity_change=0,
                                unit=new_unit,
                                note=f'Unit converted from {item.unit} to {new_unit}',
                                created_by=current_user.id,
                                quantity_used=0.0
                            )
                            db.session.add(history)
                        except Exception as e:
                            return False, f'Could not convert inventory to new unit: {str(e)}'

                    session.pop('pending_unit_change', None)

        # Update basic fields
        item.name = form_data.get('name')
        
        # Handle quantity update with recount
        new_quantity = float(form_data.get('quantity', item.quantity))
        if abs(new_quantity - item.quantity) > 0.001:
            # Use recount to set absolute quantity
            success = process_inventory_adjustment(
                item_id=item.id,
                quantity=new_quantity,  # Recount target quantity, not delta
                change_type='recount',
                notes=f'Quantity updated via edit: {item.quantity} → {new_quantity}',
                created_by=current_user.id if current_user.is_authenticated else None,
                item_type=item.type
            )
            if not success:
                return False, 'Error updating quantity'

        # Handle perishable status changes
        is_perishable = form_data.get('is_perishable') == 'on'
        was_perishable = item.is_perishable
        old_shelf_life = item.shelf_life_days
        item.is_perishable = is_perishable

        if is_perishable:
            shelf_life_days = int(form_data.get('shelf_life_days', 0))
            item.shelf_life_days = shelf_life_days
            from datetime import datetime, timedelta
            if shelf_life_days > 0:
                item.expiration_date = datetime.utcnow().date() + timedelta(days=shelf_life_days)

                if not was_perishable or old_shelf_life != shelf_life_days:
                    # Import moved to avoid circular dependency
                    from app.blueprints.expiration.services import ExpirationService
                    ExpirationService.update_fifo_expiration_data(item.id, shelf_life_days)
        else:
            if was_perishable:
                item.shelf_life_days = None
                item.expiration_date = None

                fifo_entries = InventoryHistory.query.filter(
                    and_(
                        InventoryHistory.inventory_item_id == item.id,
                        InventoryHistory.remaining_quantity > 0
                    )
                ).all()

                for entry in fifo_entries:
                    entry.is_perishable = False
                    entry.shelf_life_days = None
                    entry.expiration_date = None

        # Handle cost override
        new_cost = float(form_data.get('cost_per_unit', 0))
        if form_data.get('override_cost') and new_cost != item.cost_per_unit:
            history = InventoryHistory(
                inventory_item_id=item.id,
                change_type='cost_override',
                quantity_change=0,
                unit=item.unit,
                unit_cost=new_cost,
                note=f'Cost manually overridden from {item.cost_per_unit} to {new_cost}',
                created_by=current_user.id,
                quantity_used=0.0
            )
            db.session.add(history)
            item.cost_per_unit = new_cost

        # Type-specific updates
        if item.type == 'container':
            item.storage_amount = float(form_data.get('storage_amount'))
            item.storage_unit = form_data.get('storage_unit')
        else:
            item.unit = form_data.get('unit')
            category_id = form_data.get('category_id')
            item.category_id = None if not category_id or category_id == '' else int(category_id)
            if not item.category_id:
                item.density = float(form_data.get('density', 1.0))
            else:
                category = IngredientCategory.query.get(item.category_id)
                if category and category.default_density:
                    item.density = category.default_density
                else:
                    item.density = None

        db.session.commit()
        return True, f'{item.type.title()} updated successfully.'

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating inventory item {item_id}: {str(e)}")
        return False, f'Error saving changes: {str(e)}'