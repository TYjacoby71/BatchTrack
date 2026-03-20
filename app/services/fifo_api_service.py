"""FIFO API payload builders.

Synopsis:
Provides reusable payload builders for FIFO detail and batch inventory summary
responses so route modules can expose stable APIs without cross-blueprint imports.

Glossary:
- FIFO entry: A lot/event consumed oldest-first for inventory deductions.
- Batch usage: Lot-level inventory consumption tied to a specific batch.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import or_

from app.models import Batch, BatchContainer, ExtraBatchContainer, InventoryItem, db
from app.models.inventory_lot import InventoryLot
from app.models.unified_inventory_history import UnifiedInventoryHistory
from app.services.freshness_service import FreshnessService
from app.utils.inventory_event_code_generator import int_to_base36
from app.utils.recipe_display import format_recipe_lineage_name

logger = logging.getLogger(__name__)


def get_fifo_details_payload(inventory_id: int, *, batch_id: int | None = None) -> dict:
    item = InventoryItem.scoped().filter_by(id=inventory_id).first_or_404()

    fifo_entries = (
        UnifiedInventoryHistory.scoped().filter_by(inventory_item_id=inventory_id)
        .filter(
            or_(
                UnifiedInventoryHistory.remaining_quantity_base > 0,
                UnifiedInventoryHistory.remaining_quantity > 0,
            )
        )
        .order_by(UnifiedInventoryHistory.timestamp.asc())
        .all()
    )

    batch_usage = get_batch_fifo_usage(inventory_id, batch_id) if batch_id else []

    fifo_data = []
    for entry in fifo_entries:
        age_days = None
        life_remaining_percent = None

        if entry.timestamp:
            age_days = (datetime.now(timezone.utc) - entry.timestamp).days
            if entry.is_perishable and entry.shelf_life_days:
                life_remaining_percent = max(
                    0, 100 - ((age_days / entry.shelf_life_days) * 100)
                )
                life_remaining_percent = round(life_remaining_percent, 1)

        fifo_data.append(
            {
                "fifo_id": int_to_base36(entry.id),
                "remaining_quantity": entry.remaining_quantity,
                "unit": entry.unit,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "age_days": age_days,
                "life_remaining_percent": life_remaining_percent,
                "unit_cost": entry.unit_cost,
            }
        )

    return {
        "inventory_item": {
            "id": item.id,
            "name": item.name,
            "type": item.type,
            "quantity": item.quantity,
            "unit": item.unit,
        },
        "fifo_entries": fifo_data,
        "batch_usage": batch_usage,
    }


def get_batch_inventory_summary_payload(batch_id: int) -> dict:
    batch = Batch.scoped().filter_by(id=batch_id).first_or_404()

    ingredient_summary = build_merged_ingredient_summary(batch)

    batch_containers = BatchContainer.scoped().filter_by(batch_id=batch_id).all()
    extra_containers = ExtraBatchContainer.scoped().filter_by(batch_id=batch_id).all()

    container_summary = []
    for container in batch_containers:
        container_summary.append(
            {
                "name": container.inventory_item.container_display_name,
                "quantity_used": container.quantity_used,
                "cost_each": container.cost_each,
                "type": "regular",
            }
        )

    for extra_container in extra_containers:
        container_summary.append(
            {
                "name": extra_container.inventory_item.container_display_name,
                "quantity_used": extra_container.quantity_used,
                "cost_each": extra_container.cost_each,
                "type": "extra",
            }
        )

    try:
        freshness = FreshnessService.compute_batch_freshness(batch)
        freshness_payload = {
            "overall_freshness_percent": getattr(
                freshness, "overall_freshness_percent", None
            ),
            "items": [
                {
                    "inventory_item_id": i.inventory_item_id,
                    "item_name": i.item_name,
                    "weighted_freshness_percent": i.weighted_freshness_percent,
                    "lots_contributed": i.lots_contributed,
                    "total_used": i.total_used,
                    "unit": i.unit,
                }
                for i in getattr(freshness, "items", [])
            ],
        }
    except Exception:
        logger.warning(
            "Suppressed exception fallback at app/services/fifo_api_service.py:freshness",
            exc_info=True,
        )
        freshness_payload = {"overall_freshness_percent": None, "items": []}

    return {
        "batch": {
            "label_code": batch.label_code,
            "recipe_name": format_recipe_lineage_name(batch.recipe),
            "scale": batch.scale,
        },
        "ingredient_summary": ingredient_summary,
        "container_summary": container_summary,
        "freshness_summary": freshness_payload,
    }


def get_batch_fifo_usage(inventory_id: int, batch_id: int) -> list[dict]:
    events = (
        UnifiedInventoryHistory.scoped().filter(
            UnifiedInventoryHistory.inventory_item_id == inventory_id,
            UnifiedInventoryHistory.batch_id == batch_id,
            UnifiedInventoryHistory.change_type == "batch",
            UnifiedInventoryHistory.quantity_change < 0,
        )
        .order_by(UnifiedInventoryHistory.timestamp.asc())
        .all()
    )

    usage_data = []
    for ev in events:
        age_days = None
        life_remaining_percent = None
        lot_display_id = None
        when = ev.timestamp or datetime.now(timezone.utc)

        if ev.affected_lot_id:
            lot = db.session.get(InventoryLot, ev.affected_lot_id)
            lot_display_id = (
                lot.lot_number
                if getattr(lot, "lot_number", None)
                else int_to_base36(ev.affected_lot_id)
            )
            if lot and getattr(lot, "received_date", None):
                try:
                    age_days = max(0, (when - lot.received_date).days)
                except Exception:
                    logger.warning(
                        "Suppressed exception fallback at app/services/fifo_api_service.py:batch_usage_age",
                        exc_info=True,
                    )
                    age_days = None
            try:
                life_remaining_percent = (
                    FreshnessService._compute_lot_freshness_percent_at_time(  # type: ignore
                        lot, when
                    )
                )
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/services/fifo_api_service.py:batch_usage_freshness",
                    exc_info=True,
                )
                life_remaining_percent = None

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

                    life_remaining_percent = (
                        FreshnessService._compute_lot_freshness_percent_at_time(  # type: ignore
                            _FakeLot, when
                        )
                    )
                    age_days = (when - received_guess).days
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/services/fifo_api_service.py:batch_usage_fallback",
                    exc_info=True,
                )

        usage_data.append(
            {
                "fifo_id": lot_display_id or int_to_base36(ev.id),
                "quantity_used": abs(float(ev.quantity_change or 0.0)),
                "unit": ev.unit,
                "age_days": age_days,
                "life_remaining_percent": life_remaining_percent,
                "unit_cost": float(ev.unit_cost or 0.0),
            }
        )

    return usage_data


def build_merged_ingredient_summary(batch: Batch) -> list[dict]:
    events = (
        UnifiedInventoryHistory.scoped().filter(
            UnifiedInventoryHistory.batch_id == batch.id,
            UnifiedInventoryHistory.change_type == "batch",
            UnifiedInventoryHistory.quantity_change < 0,
        )
        .order_by(UnifiedInventoryHistory.timestamp.asc())
        .all()
    )

    per_item: dict[int, list[UnifiedInventoryHistory]] = {}
    for ev in events:
        per_item.setdefault(ev.inventory_item_id, []).append(ev)

    ingredient_summary = []
    for inventory_item_id, evs in per_item.items():
        item = db.session.get(InventoryItem, inventory_item_id)
        if not item:
            continue

        usage_data = []
        for ev in evs:
            age_days = None
            life_remaining_percent = None
            lot_display_id = None
            when = ev.timestamp or datetime.now(timezone.utc)

            if ev.affected_lot_id:
                lot = db.session.get(InventoryLot, ev.affected_lot_id)
                lot_display_id = (
                    lot.lot_number
                    if getattr(lot, "lot_number", None)
                    else int_to_base36(ev.affected_lot_id)
                )
                if lot and getattr(lot, "received_date", None):
                    try:
                        age_days = max(0, (when - lot.received_date).days)
                    except Exception:
                        logger.warning(
                            "Suppressed exception fallback at app/services/fifo_api_service.py:summary_age",
                            exc_info=True,
                        )
                        age_days = None
                try:
                    life_remaining_percent = (
                        FreshnessService._compute_lot_freshness_percent_at_time(  # type: ignore
                            lot, when
                        )
                    )
                except Exception:
                    logger.warning(
                        "Suppressed exception fallback at app/services/fifo_api_service.py:summary_freshness",
                        exc_info=True,
                    )
                    life_remaining_percent = None

            if (
                life_remaining_percent is None
                and item.is_perishable
                and item.shelf_life_days
            ):
                try:
                    from datetime import timedelta

                    received_guess = when - timedelta(days=int(item.shelf_life_days))

                    class _FakeLot:
                        received_date = received_guess
                        expiration_date = when
                        shelf_life_days = item.shelf_life_days
                        inventory_item = item

                    life_remaining_percent = (
                        FreshnessService._compute_lot_freshness_percent_at_time(  # type: ignore
                            _FakeLot, when
                        )
                    )
                    age_days = (when - received_guess).days
                except Exception:
                    logger.warning(
                        "Suppressed exception fallback at app/services/fifo_api_service.py:summary_fallback",
                        exc_info=True,
                    )

            usage_data.append(
                {
                    "fifo_id": lot_display_id or int_to_base36(ev.id),
                    "quantity_used": abs(float(ev.quantity_change or 0.0)),
                    "unit": ev.unit,
                    "age_days": age_days,
                    "life_remaining_percent": life_remaining_percent,
                    "unit_cost": float(ev.unit_cost or 0.0),
                }
            )

        ingredient_summary.append(
            {
                "name": item.name,
                "inventory_item_id": inventory_item_id,
                "total_used": sum(u["quantity_used"] for u in usage_data),
                "unit": item.unit,
                "fifo_usage": usage_data,
            }
        )

    ingredient_summary.sort(key=lambda x: x["name"].lower())
    return ingredient_summary
