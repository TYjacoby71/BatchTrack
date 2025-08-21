
"""
Inventory Item Creation Logic

Handles the creation of new inventory items and their initial stock entries.
"""

import logging
from datetime import datetime
from app.models import db, InventoryItem
from ._fifo_ops import add_to_fifo

logger = logging.getLogger(__name__)


def handle_initial_stock(item, quantity, change_type, **kwargs):
    """
    Handles the special case for an item's very first stock entry.
    
    For initial stock, we always treat it as an additive operation
    and delegate to the FIFO expert.
    """
    logger.info(f"Handling initial stock for item {item.id}: {quantity}")
    
    # The first entry for an item is ALWAYS an additive operation
    # We delegate immediately to the FIFO expert
    return add_to_fifo(item, quantity, 'initial_stock', **kwargs)


def create_inventory_item(form_data, organization_id, created_by):
    """
    Creates a new inventory item and optionally adds initial stock.
    
    This function creates the item first, then uses the canonical
    inventory adjustment service to add initial stock.
    """
    try:
        # Extract form data
        name = form_data.get('name', '').strip()
        category_id = form_data.get('category_id')
        unit = form_data.get('unit', 'unit')
        quantity = float(form_data.get('quantity', 0.0))
        
        # Basic validation
        if not name:
            return False, "Item name is required.", None
            
        # Create the inventory item
        item = InventoryItem(
            name=name,
            category_id=category_id if category_id else None,
            unit=unit,
            quantity=0.0,  # Start with 0, will be updated by inventory adjustment
            organization_id=organization_id,
            created_by=created_by,
            created_at=datetime.utcnow()
        )
        
        db.session.add(item)
        db.session.flush()  # Get the item ID without committing
        
        # If there's initial quantity, use the canonical inventory adjustment service
        if quantity > 0:
            from ._core import process_inventory_adjustment
            
            # Extract additional parameters
            unit_cost = float(form_data.get('unit_cost', 0.0))
            received_date = form_data.get('received_date')
            expiration_date = form_data.get('expiration_date')
            source_notes = form_data.get('source_notes', '')
            
            success, message = process_inventory_adjustment(
                item_id=item.id,
                quantity=quantity,
                change_type='restock',  # First entry is a restock
                created_by=created_by,
                unit_cost=unit_cost,
                received_date=received_date,
                expiration_date=expiration_date,
                source_notes=source_notes
            )
            
            if not success:
                db.session.rollback()
                logger.error(f"Failed to add initial stock: {message}")
                return False, f"Failed to add initial stock: {message}", None
        
        db.session.commit()
        logger.info(f"Successfully created item {item.id} with initial quantity {quantity}")
        return True, "Item created successfully.", item.id
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating inventory item: {e}", exc_info=True)
        return False, f"Error creating item: {str(e)}", None
