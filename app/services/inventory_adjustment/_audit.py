"""
Audit Trail Management for Inventory Adjustments

This module handles all audit trail and history recording for inventory operations.
"""

from datetime import datetime
from flask_login import current_user
from app.models import db, InventoryItem, UnifiedInventoryHistory
from app.utils.fifo_generator import generate_fifo_code
import logging

logger = logging.getLogger(__name__)


def audit_event(
    item_id: int,
    change_type: str,
    notes: str = "",
    created_by: int = None,
    item_type: str = "ingredient",
    fifo_reference_id: int = None,
    unit: str = None,
    unit_cost: float = None,
) -> bool:
    """
    Sanctioned audit-only history entry (no inventory change).
    Uses the same internal helpers so nothing writes outside this module.
    """
    try:
        item = InventoryItem.query.get(item_id)
        if not item:
            return False

        fifo_code = generate_fifo_code(change_type, 0)

        # Use unified history table for all audit entries
        history = UnifiedInventoryHistory(
            inventory_item_id=item_id,
            change_type=change_type,
            quantity_change=0.0,  # Audit entries don't change quantity
            remaining_quantity=0.0,  # Audit entries have no FIFO impact
            unit=unit or item.unit,
            notes=notes,
            created_by=created_by,
            organization_id=item.organization_id,  # Trust middleware handled auth
            fifo_code=fifo_code,
            fifo_reference_id=fifo_reference_id,
            unit_cost=unit_cost
        )

        db.session.add(history)
        db.session.commit()
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating audit entry: {str(e)}")
        return False


def record_audit_entry(
    item_id: int,
    change_type: str,
    quantity_change: float = 0,
    notes: str | None = None,
    created_by: int | None = None,
    unit: str = None,
    unit_cost: float = None,
    remaining_quantity: float = 0,
    fifo_reference_id: int = None,
    fifo_code: str | None = None,
    batch_id: str | None = None,
    quantity_used: float = 0,
    used_for_batch_id: str | None = None,
    is_perishable: bool | None = None,
    shelf_life_days: int | None = None,
    expiration_date: datetime | None = None,
    location_id: int | None = None,
    location_name: str | None = None,
    temperature_at_time: float | None = None,
    quality_status: str | None = None,
    compliance_status: str | None = None,
    quality_checked_by: int | None = None,
    customer: str | None = None,
    sale_price: float | None = None,
    order_id: str | None = None,
    reservation_id: str | None = None,
    is_reserved: bool | None = None,
    sale_location: str | None = None,
    marketplace_order_id: str | None = None,
    marketplace_source: str | None = None,
    batch_number: str | None = None,
    lot_number: str | None = None,
    container_id: str | None = None,
    fifo_source: str | None = None,
    data: list | dict | None = None,
) -> bool:
    """
    Record an audit trail entry for inventory operations.

    This is used for operations that need to log activity but don't affect FIFO lots,
    such as cost overrides, administrative changes, etc.
    """
    try:
        # Handle both individual parameters and bulk data
        if isinstance(data, list):
            # Bulk insert - data is a list of dictionaries
            for entry_data in data:
                # Ensure required fields have defaults
                entry_data.setdefault('timestamp', datetime.utcnow())
                entry_data.setdefault('organization_id', current_user.organization_id if current_user.is_authenticated else None)

                # Ensure quantity_change is a float, not a string
                if 'quantity_change' in entry_data:
                    if isinstance(entry_data['quantity_change'], str):
                        # Extract numeric part if it's a formatted string
                        import re
                        numeric_match = re.search(r'[\d.]+', entry_data['quantity_change'])
                        if numeric_match:
                            entry_data['quantity_change'] = float(numeric_match.group())
                        else:
                            entry_data['quantity_change'] = 0.0
                    else:
                        entry_data['quantity_change'] = float(entry_data['quantity_change'] or 0)

                # Ensure unit is provided
                if 'unit' not in entry_data or entry_data['unit'] is None:
                    entry_data['unit'] = 'count'  # Default unit

            db.session.execute(UnifiedInventoryHistory.__table__.insert(), data)
        else:
            # Single entry - construct from individual parameters
            # Ensure unit is provided
            if unit is None:
                unit = 'count'  # Default unit

            # Ensure quantity_change is numeric
            if isinstance(quantity_change, str):
                import re
                numeric_match = re.search(r'[\d.]+', str(quantity_change))
                if numeric_match:
                    quantity_change = float(numeric_match.group())
                else:
                    quantity_change = 0.0
            else:
                quantity_change = float(quantity_change or 0)

            entry_data = {
                'inventory_item_id': item_id,
                'timestamp': datetime.utcnow(),
                'change_type': change_type,
                'quantity_change': quantity_change,
                'unit': unit,
                'unit_cost': unit_cost,
                'remaining_quantity': remaining_quantity or 0,
                'fifo_reference_id': fifo_reference_id,
                'fifo_code': fifo_code,
                'batch_id': batch_id,
                'created_by': created_by,  # Trust caller to provide this
                'notes': notes or '',
                'quantity_used': quantity_used or 0,
                'used_for_batch_id': used_for_batch_id,
                'is_perishable': int(bool(is_perishable)) if is_perishable is not None else 0,
                'shelf_life_days': shelf_life_days,
                'expiration_date': expiration_date,
                'location_id': location_id,
                'location_name': location_name,
                'temperature_at_time': temperature_at_time,
                'quality_status': quality_status,
                'compliance_status': compliance_status,
                'quality_checked_by': quality_checked_by,
                'customer': customer,
                'sale_price': sale_price,
                'order_id': order_id,
                'reservation_id': reservation_id,
                'is_reserved': int(bool(is_reserved)) if is_reserved is not None else 0,
                'sale_location': sale_location,
                'marketplace_order_id': marketplace_order_id,
                'marketplace_source': marketplace_source,
                'batch_number': batch_number,
                'lot_number': lot_number,
                'container_id': container_id,
                'fifo_source': fifo_source,
                'organization_id': None  # Will be handled by model/middleware if needed
            }

            entry = UnifiedInventoryHistory(**entry_data)
            db.session.add(entry)

        db.session.commit()
        logger.info(f"Recorded audit entry for item {item_id}: {change_type}")
        return True

    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to record audit entry for item {item_id}: {e}")
        return False