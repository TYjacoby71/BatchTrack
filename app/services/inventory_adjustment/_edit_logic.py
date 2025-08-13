
import logging
from datetime import datetime
from app.models import db, InventoryItem, IngredientCategory, UnifiedInventoryHistory
from app.services.unit_conversion import ConversionEngine
from ._validation import validate_inventory_fifo_sync
from ._fifo_ops import _internal_add_fifo_entry_enhanced

logger = logging.getLogger(__name__)

def update_inventory_item(item_id, updates, current_user_id=None):
    """
    Update inventory item details while maintaining FIFO integrity.
    
    Args:
        item_id: ID of the inventory item to update
        updates: Dictionary of fields to update
        current_user_id: ID of user making the update
        
    Returns:
        tuple: (success: bool, error_message: str or None, updated_item: InventoryItem or None)
    """
    try:
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, f"Item {item_id} not found", None
            
        # Store original values for audit trail
        original_values = {}
        
        # Handle category updates
        if 'category_id' in updates:
            category_id = updates['category_id']
            if category_id:
                category = db.session.get(IngredientCategory, category_id)
                if not category:
                    return False, f"Category {category_id} not found", None
                if category.organization_id != item.organization_id:
                    return False, "Category belongs to different organization", None
                    
                original_values['category_id'] = item.category_id
                item.category_id = category_id
                
        # Handle name updates
        if 'name' in updates:
            original_values['name'] = item.name
            item.name = updates['name'].strip()
            
        # Handle unit updates
        if 'unit' in updates:
            new_unit = updates['unit']
            if new_unit != item.unit:
                # Validate unit conversion is possible
                try:
                    # Test conversion to ensure units are compatible
                    test_conversion = ConversionEngine.convert_units(
                        1.0, item.unit, new_unit, item_type=item.type
                    )
                    original_values['unit'] = item.unit
                    item.unit = new_unit
                except Exception as e:
                    return False, f"Unit conversion error: {str(e)}", None
                    
        # Handle cost updates
        if 'cost_per_unit' in updates:
            try:
                new_cost = float(updates['cost_per_unit'])
                if new_cost < 0:
                    return False, "Cost per unit cannot be negative", None
                original_values['cost_per_unit'] = item.cost_per_unit
                item.cost_per_unit = new_cost
            except (ValueError, TypeError):
                return False, "Invalid cost per unit value", None
                
        # Handle notes updates
        if 'notes' in updates:
            original_values['notes'] = item.notes
            item.notes = updates['notes']
            
        # Handle expiration date updates
        if 'expiration_date' in updates:
            original_values['expiration_date'] = item.expiration_date
            item.expiration_date = updates['expiration_date']
            
        # Handle minimum stock level updates
        if 'minimum_stock_level' in updates:
            try:
                new_min = float(updates['minimum_stock_level']) if updates['minimum_stock_level'] else None
                if new_min is not None and new_min < 0:
                    return False, "Minimum stock level cannot be negative", None
                original_values['minimum_stock_level'] = item.minimum_stock_level
                item.minimum_stock_level = new_min
            except (ValueError, TypeError):
                return False, "Invalid minimum stock level value", None
                
        # Update timestamps
        item.updated_at = datetime.utcnow()
        
        # Commit the changes
        db.session.commit()
        
        # Validate FIFO sync after update
        is_valid, error_msg, inventory_qty, fifo_total = validate_inventory_fifo_sync(
            item_id, item.type
        )
        
        if not is_valid:
            logger.warning(f"FIFO sync warning after item update: {error_msg}")
            
        logger.info(f"Updated inventory item {item_id}: {original_values}")
        return True, None, item
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating inventory item {item_id}: {e}")
        return False, f"Update failed: {str(e)}", None
