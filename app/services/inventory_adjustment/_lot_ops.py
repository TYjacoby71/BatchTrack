
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.models.inventory_lot import InventoryLot
from app.utils.timezone_utils import TimezoneUtils

logger = logging.getLogger(__name__)


def create_inventory_lot(
    item_id: int,
    quantity: float,
    unit: str,
    unit_cost: float,
    source_type: str,
    source_notes: str = None,
    created_by: int = None,
    expiration_date: datetime = None,
    shelf_life_days: int = None,
    **kwargs
) -> Tuple[bool, str, Optional[InventoryLot]]:
    """
    Create a new inventory lot for FIFO tracking.
    
    Returns: (success, message, lot)
    """
    try:
        # Get item for validation
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, f"Item {item_id} not found", None
        
        # Validate quantity
        if quantity <= 0:
            return False, "Quantity must be positive", None
        
        # Handle expiration
        final_expiration = expiration_date
        if not final_expiration and shelf_life_days and shelf_life_days > 0:
            final_expiration = TimezoneUtils.utc_now() + timedelta(days=shelf_life_days)
        
        # Generate FIFO code
        from app.utils.fifo_generator import get_fifo_prefix
        fifo_code = get_fifo_prefix(source_type, True)  # True for additive
        
        # Create the lot
        lot = InventoryLot(
            inventory_item_id=item_id,
            remaining_quantity=quantity,
            original_quantity=quantity,
            unit=unit,
            unit_cost=unit_cost,
            source_type=source_type,
            source_notes=source_notes,
            created_by=created_by,
            expiration_date=final_expiration,
            shelf_life_days=shelf_life_days,
            fifo_code=fifo_code,
            organization_id=item.organization_id
        )
        
        db.session.add(lot)
        db.session.flush()  # Get ID
        
        # Create event record
        event = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=source_type,
            quantity_change=quantity,
            unit=unit,
            unit_cost=unit_cost,
            notes=source_notes or f"Created lot {lot.id}",
            created_by=created_by,
            timestamp=TimezoneUtils.utc_now(),
            affected_lot_id=lot.id,
            # Legacy fields for compatibility
            remaining_quantity=0,  # Events don't track remaining quantity
        )
        
        db.session.add(event)
        
        # Update item quantity
        item.quantity += quantity
        
        logger.info(f"LOT: Created lot {lot.id} with {quantity} {unit} for item {item_id}")
        
        return True, f"Created lot with {quantity} {unit}", lot
        
    except Exception as e:
        logger.error(f"Error creating inventory lot: {str(e)}")
        return False, str(e), None


def consume_from_lots_fifo(
    item_id: int,
    quantity: float,
    change_type: str,
    notes: str = None,
    created_by: int = None,
    **kwargs
) -> Tuple[bool, str]:
    """
    Consume inventory using FIFO lot system.
    
    Returns: (success, message)
    """
    try:
        # Get item
        item = db.session.get(InventoryItem, item_id)
        if not item:
            return False, f"Item {item_id} not found"
        
        # Get available lots in FIFO order (oldest first)
        available_lots = InventoryLot.query.filter(
            InventoryLot.inventory_item_id == item_id,
            InventoryLot.remaining_quantity > 0
        ).order_by(InventoryLot.received_date.asc()).all()
        
        # Check if we have enough inventory
        total_available = sum(lot.remaining_quantity for lot in available_lots)
        if total_available < quantity:
            return False, f"Insufficient inventory: need {quantity}, have {total_available}"
        
        # Execute FIFO consumption
        remaining_to_consume = quantity
        consumed_lots = []
        
        for lot in available_lots:
            if remaining_to_consume <= 0:
                break
            
            consume_from_lot = min(lot.remaining_quantity, remaining_to_consume)
            
            # Consume from this lot
            success = lot.consume(consume_from_lot)
            if not success:
                return False, f"Failed to consume from lot {lot.id}"
            
            consumed_lots.append({
                'lot_id': lot.id,
                'consumed': consume_from_lot,
                'remaining': lot.remaining_quantity
            })
            
            remaining_to_consume -= consume_from_lot
        
        # Create event record
        event = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            organization_id=item.organization_id,
            change_type=change_type,
            quantity_change=-quantity,  # Negative for consumption
            unit=item.unit or 'count',
            notes=notes or f"FIFO consumption from {len(consumed_lots)} lots",
            created_by=created_by,
            timestamp=TimezoneUtils.utc_now(),
            # Don't reference specific lot since multiple lots were affected
            remaining_quantity=0,  # Events don't track remaining quantity
        )
        
        db.session.add(event)
        
        # Update item quantity
        item.quantity -= quantity
        
        logger.info(f"LOT: Consumed {quantity} from {len(consumed_lots)} lots for item {item_id}")
        
        return True, f"Consumed {quantity} {item.unit or 'units'} using FIFO"
        
    except Exception as e:
        logger.error(f"Error consuming from lots: {str(e)}")
        return False, str(e)


def get_lot_summary(item_id: int) -> dict:
    """Get summary of all lots for an item"""
    try:
        lots = InventoryLot.query.filter(
            InventoryLot.inventory_item_id == item_id,
            InventoryLot.remaining_quantity > 0
        ).order_by(InventoryLot.received_date.asc()).all()
        
        total_quantity = sum(lot.remaining_quantity for lot in lots)
        expired_lots = [lot for lot in lots if lot.is_expired]
        expiring_soon = [lot for lot in lots if lot.expiration_date and 
                        lot.expiration_date < datetime.utcnow() + timedelta(days=7)]
        
        return {
            'total_lots': len(lots),
            'total_quantity': total_quantity,
            'expired_lots': len(expired_lots),
            'expiring_soon': len(expiring_soon),
            'lots': [{
                'id': lot.id,
                'remaining_quantity': lot.remaining_quantity,
                'original_quantity': lot.original_quantity,
                'unit_cost': lot.unit_cost,
                'received_date': lot.received_date,
                'expiration_date': lot.expiration_date,
                'is_expired': lot.is_expired,
                'source_type': lot.source_type
            } for lot in lots]
        }
        
    except Exception as e:
        logger.error(f"Error getting lot summary: {str(e)}")
        return {'error': str(e)}
