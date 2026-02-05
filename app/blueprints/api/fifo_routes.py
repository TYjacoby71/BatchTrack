"""FIFO detail API routes.

Synopsis:
Provide FIFO lot details and batch usage summaries for inventory items.

Glossary:
- FIFO entry: A lot event displayed in FIFO ordering.
- Batch usage: Lot consumption tied to a batch.
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.utils.permissions import require_permission
from ...models import (
    db,
    InventoryItem,
    Batch,
    BatchIngredient,
    ExtraBatchIngredient,
    BatchContainer,
    ExtraBatchContainer,
)
from ...models.unified_inventory_history import UnifiedInventoryHistory
from ...models.inventory_lot import InventoryLot
from ...services.freshness_service import FreshnessService
from datetime import datetime, date
from sqlalchemy import or_
from ...utils.inventory_event_code_generator import int_to_base36

fifo_api_bp = Blueprint('fifo_api', __name__)

@fifo_api_bp.route('/api/fifo-details/<int:inventory_id>')
@login_required
@require_permission('inventory.view')
def get_fifo_details(inventory_id):
    try:
        batch_id = request.args.get('batch_id', type=int)
        
        # Get inventory item
        item = InventoryItem.query.get_or_404(inventory_id)
        
        # Get current FIFO entries (available stock) from UnifiedInventoryHistory
        fifo_entries = UnifiedInventoryHistory.query.filter_by(inventory_item_id=inventory_id) \
            .filter(
                or_(
                    UnifiedInventoryHistory.remaining_quantity_base > 0,
                    UnifiedInventoryHistory.remaining_quantity > 0
                )
            ) \
            .order_by(UnifiedInventoryHistory.timestamp.asc()).all()
        
        # Get batch usage if batch_id provided
        batch_usage = []
        if batch_id:
            batch_usage = get_batch_fifo_usage(inventory_id, batch_id)
        
        # Process FIFO entries
        fifo_data = []
        for entry in fifo_entries:
            age_days = None
            life_remaining_percent = None
            
            if entry.timestamp:
                age_days = (datetime.now(timezone.utc) - entry.timestamp).days
                
                if entry.is_perishable and entry.shelf_life_days:
                    life_remaining_percent = max(0, 100 - ((age_days / entry.shelf_life_days) * 100))
                    life_remaining_percent = round(life_remaining_percent, 1)
            
            fifo_data.append({
                'fifo_id': int_to_base36(entry.id),
                'remaining_quantity': entry.remaining_quantity,
                'unit': entry.unit,
                'timestamp': entry.timestamp.isoformat() if entry.timestamp else None,
                'age_days': age_days,
                'life_remaining_percent': life_remaining_percent,
                'unit_cost': entry.unit_cost
            })
        
        return jsonify({
            'inventory_item': {
                'id': item.id,
                'name': item.name,
                'type': item.type,
                'quantity': item.quantity,
                'unit': item.unit
            },
            'fifo_entries': fifo_data,
            'batch_usage': batch_usage
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@fifo_api_bp.route('/api/batch-inventory-summary/<int:batch_id>')
@login_required
@require_permission('batches.view')
def get_batch_inventory_summary(batch_id):
    try:
        # Get batch
        batch = Batch.query.get_or_404(batch_id)
        
        # Build merged ingredient summary from unified inventory events (covers regular and extra usage)
        ingredient_summary = build_merged_ingredient_summary(batch)
        
        # Add containers
        batch_containers = BatchContainer.query.filter_by(batch_id=batch_id).all()
        extra_containers = ExtraBatchContainer.query.filter_by(batch_id=batch_id).all()
        
        container_summary = []
        for container in batch_containers:
            container_summary.append({
                'name': container.inventory_item.container_display_name,
                'quantity_used': container.quantity_used,
                'cost_each': container.cost_each,
                'type': 'regular'
            })
        
        for extra_container in extra_containers:
            container_summary.append({
                'name': extra_container.inventory_item.container_display_name,
                'quantity_used': extra_container.quantity_used,
                'cost_each': extra_container.cost_each,
                'type': 'extra'
            })
        
        # Compute freshness summary to surface in modal
        try:
            freshness = FreshnessService.compute_batch_freshness(batch)
            freshness_payload = {
                'overall_freshness_percent': getattr(freshness, 'overall_freshness_percent', None),
                'items': [
                    {
                        'inventory_item_id': i.inventory_item_id,
                        'item_name': i.item_name,
                        'weighted_freshness_percent': i.weighted_freshness_percent,
                        'lots_contributed': i.lots_contributed,
                        'total_used': i.total_used,
                        'unit': i.unit,
                    }
                    for i in getattr(freshness, 'items', [])
                ]
            }
        except Exception as e:
            freshness_payload = {
                'overall_freshness_percent': None,
                'items': []
            }

        return jsonify({
            'batch': {
                'label_code': batch.label_code,
                'recipe_name': batch.recipe.name,
                'scale': batch.scale
            },
            'ingredient_summary': ingredient_summary,
            'container_summary': container_summary,
            'freshness_summary': freshness_payload
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_batch_fifo_usage(inventory_id, batch_id):
    """Get lot-level usage data for a specific ingredient in a specific batch using unified events."""
    events = UnifiedInventoryHistory.query.filter(
        UnifiedInventoryHistory.inventory_item_id == inventory_id,
        UnifiedInventoryHistory.batch_id == batch_id,
        UnifiedInventoryHistory.change_type == 'batch',
        UnifiedInventoryHistory.quantity_change < 0
    ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

    # Build usage entries; aggregate by affected lot when possible
    usage_data = []

    for ev in events:
        age_days = None
        life_remaining_percent = None
        lot_display_id = None

        when = ev.timestamp or datetime.now(timezone.utc)

        if ev.affected_lot_id:
            lot = db.session.get(InventoryLot, ev.affected_lot_id)
            lot_display_id = lot.lot_number if getattr(lot, 'lot_number', None) else int_to_base36(ev.affected_lot_id)

            if lot and getattr(lot, 'received_date', None):
                try:
                    age_days = max(0, (when - lot.received_date).days)
                except Exception:
                    age_days = None

            # Compute freshness percent using shared logic
            try:
                life_remaining_percent = FreshnessService._compute_lot_freshness_percent_at_time(lot, when)  # type: ignore
            except Exception:
                life_remaining_percent = None

        # Fallback freshness computation if lot is missing but item has shelf life
        if life_remaining_percent is None:
            try:
                item = db.session.get(InventoryItem, inventory_id)
                if item and item.is_perishable and item.shelf_life_days:
                    from datetime import timedelta
                    received_guess = when - timedelta(days=int(item.shelf_life_days))
                    class _FakeLot:
                        received_date = received_guess
                        expiration_date = when
                        shelf_life_days = item.shelf_life_days
                        inventory_item = item
                    life_remaining_percent = FreshnessService._compute_lot_freshness_percent_at_time(_FakeLot, when)  # type: ignore
                    age_days = (when - received_guess).days
            except Exception:
                pass

        usage_data.append({
            'fifo_id': lot_display_id or int_to_base36(ev.id),
            'quantity_used': abs(float(ev.quantity_change or 0.0)),
            'unit': ev.unit,
            'age_days': age_days,
            'life_remaining_percent': life_remaining_percent,
            'unit_cost': float(ev.unit_cost or 0.0)
        })

    return usage_data


def build_merged_ingredient_summary(batch: Batch):
    """Return merged ingredient summary across regular and extra usage, grouped by inventory item.

    Uses UnifiedInventoryHistory events to ensure all deductions are included.
    """
    # Gather all deduction events for this batch
    events = UnifiedInventoryHistory.query.filter(
        UnifiedInventoryHistory.batch_id == batch.id,
        UnifiedInventoryHistory.change_type == 'batch',
        UnifiedInventoryHistory.quantity_change < 0
    ).order_by(UnifiedInventoryHistory.timestamp.asc()).all()

    per_item = {}
    for ev in events:
        per_item.setdefault(ev.inventory_item_id, []).append(ev)

    ingredient_summary = []
    for inventory_item_id, evs in per_item.items():
        item = db.session.get(InventoryItem, inventory_item_id)
        if not item:
            continue

        usage_data = []
        for ev in evs:
            # Reuse the same computation as get_batch_fifo_usage for each event
            # but avoid re-querying by inventory id; inline minimal logic
            age_days = None
            life_remaining_percent = None
            lot_display_id = None
            when = ev.timestamp or datetime.now(timezone.utc)

            if ev.affected_lot_id:
                lot = db.session.get(InventoryLot, ev.affected_lot_id)
                lot_display_id = lot.lot_number if getattr(lot, 'lot_number', None) else int_to_base36(ev.affected_lot_id)
                if lot and getattr(lot, 'received_date', None):
                    try:
                        age_days = max(0, (when - lot.received_date).days)
                    except Exception:
                        age_days = None
                try:
                    life_remaining_percent = FreshnessService._compute_lot_freshness_percent_at_time(lot, when)  # type: ignore
                except Exception:
                    life_remaining_percent = None

            if life_remaining_percent is None and item and item.is_perishable and item.shelf_life_days:
                try:
                    from datetime import timedelta
                    received_guess = when - timedelta(days=int(item.shelf_life_days))
                    class _FakeLot:
                        received_date = received_guess
                        expiration_date = when
                        shelf_life_days = item.shelf_life_days
                        inventory_item = item
                    life_remaining_percent = FreshnessService._compute_lot_freshness_percent_at_time(_FakeLot, when)  # type: ignore
                    age_days = (when - received_guess).days
                except Exception:
                    pass

            usage_data.append({
                'fifo_id': lot_display_id or int_to_base36(ev.id),
                'quantity_used': abs(float(ev.quantity_change or 0.0)),
                'unit': ev.unit,
                'age_days': age_days,
                'life_remaining_percent': life_remaining_percent,
                'unit_cost': float(ev.unit_cost or 0.0)
            })

        total_used = sum(u['quantity_used'] for u in usage_data)
        ingredient_summary.append({
            'name': item.name,
            'inventory_item_id': inventory_item_id,
            'total_used': total_used,
            'unit': item.unit,
            'fifo_usage': usage_data
        })

    # Sort alphabetically by item name
    ingredient_summary.sort(key=lambda x: x['name'].lower())
    return ingredient_summary
