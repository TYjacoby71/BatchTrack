import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from flask_login import current_user

from app.models import db
from app.models.batch import Batch
from app.models.inventory import InventoryItem
from app.models.inventory_lot import InventoryLot
from app.models.unified_inventory_history import UnifiedInventoryHistory

logger = logging.getLogger(__name__)


@dataclass
class ItemFreshness:
    inventory_item_id: int
    item_name: str
    weighted_freshness_percent: Optional[float]
    lots_contributed: int
    total_used: float
    unit: str


@dataclass
class BatchFreshnessSummary:
    batch_id: int
    overall_freshness_percent: Optional[float]
    items: List[ItemFreshness]


class FreshnessService:
    """Compute freshness metrics for batches and their consumed inventory.

    Freshness is defined as percentage of shelf-life remaining at the time of consumption,
    weighted by the quantity drawn from each lot.
    """

    @staticmethod
    def _compute_lot_freshness_percent_at_time(
        lot: InventoryLot, when: datetime
    ) -> Optional[float]:
        """Compute freshness percent of a lot at a given time.

        freshness = max(0, min(100, (expiration - when) / (expiration - received_date) * 100))

        If expiration is missing, try deriving from shelf_life_days; if still missing, return None.
        """
        try:
            if not lot:
                return None

            received = lot.received_date
            expiration = lot.expiration_date

            if not received:
                return None

            if not expiration:
                # Derive expiration when possible
                if lot.shelf_life_days:
                    expiration = received + timedelta(days=int(lot.shelf_life_days))
                elif (
                    lot.inventory_item
                    and lot.inventory_item.is_perishable
                    and lot.inventory_item.shelf_life_days
                ):
                    expiration = received + timedelta(
                        days=int(lot.inventory_item.shelf_life_days)
                    )
                else:
                    return None

            # Ensure monotonicity
            total_seconds = (expiration - received).total_seconds()
            if total_seconds <= 0:
                return 0.0

            remaining_seconds = (expiration - when).total_seconds()
            freshness = (remaining_seconds / total_seconds) * 100.0
            return round(max(0.0, min(100.0, freshness)), 1)

        except Exception as e:
            logger.warning(f"Error computing lot freshness: {e}")
            return None

    @staticmethod
    def _get_batch_consumption_events(batch_id: int) -> List[UnifiedInventoryHistory]:
        """Fetch all deduction events for a batch, joined with lots for freshness computation."""
        events = (
            UnifiedInventoryHistory.query.filter(
                UnifiedInventoryHistory.batch_id == batch_id,
                UnifiedInventoryHistory.change_type == "batch",
                UnifiedInventoryHistory.quantity_change < 0,
            )
            .order_by(UnifiedInventoryHistory.timestamp.asc())
            .all()
        )
        return events

    @staticmethod
    def compute_item_freshness_for_batch(batch: Batch) -> List[ItemFreshness]:
        """Compute weighted freshness for each inventory item consumed by the batch."""
        if not batch:
            return []

        # Scope by org for safety
        if (
            current_user.is_authenticated
            and batch.organization_id != current_user.organization_id
        ):
            return []

        events = FreshnessService._get_batch_consumption_events(batch.id)
        if not events:
            return []

        # Group events by inventory_item_id
        per_item: Dict[int, List[UnifiedInventoryHistory]] = {}
        for ev in events:
            per_item.setdefault(ev.inventory_item_id, []).append(ev)

        results: List[ItemFreshness] = []
        for item_id, evs in per_item.items():
            item: InventoryItem = db.session.get(InventoryItem, item_id)
            if not item:
                continue

            total_used = 0.0
            total_weighted = 0.0
            lots_contributed = 0

            for ev in evs:
                # quantity_change is negative for deductions
                used_amount = abs(float(ev.quantity_change or 0.0))
                if used_amount <= 0:
                    continue

                freshness_percent = None
                if ev.affected_lot_id:
                    lot = db.session.get(InventoryLot, ev.affected_lot_id)
                    if lot:
                        freshness_percent = (
                            FreshnessService._compute_lot_freshness_percent_at_time(
                                lot, ev.timestamp or datetime.now(timezone.utc)
                            )
                        )
                        lots_contributed += 1

                # Fallback: if lot freshness can't be computed, try item's shelf life against event time
                if (
                    freshness_percent is None
                    and item.is_perishable
                    and item.shelf_life_days
                    and ev.timestamp
                ):
                    received_guess = ev.timestamp - timedelta(
                        days=int(item.shelf_life_days)
                    )

                    class _FakeLot:
                        received_date = received_guess
                        expiration_date = ev.timestamp
                        shelf_life_days = item.shelf_life_days
                        inventory_item = item

                    freshness_percent = (
                        FreshnessService._compute_lot_freshness_percent_at_time(
                            _FakeLot, ev.timestamp
                        )
                    )

                if freshness_percent is None:
                    # Skip contribution if freshness unknowable
                    continue

                total_used += used_amount
                total_weighted += freshness_percent * used_amount

            if total_used > 0:
                results.append(
                    ItemFreshness(
                        inventory_item_id=item_id,
                        item_name=item.name,
                        weighted_freshness_percent=round(
                            total_weighted / total_used, 1
                        ),
                        lots_contributed=lots_contributed,
                        total_used=total_used,
                        unit=item.unit or "",
                    )
                )

        # Sort by lowest freshness first to highlight risk
        results.sort(
            key=lambda r: (
                r.weighted_freshness_percent is None,
                r.weighted_freshness_percent or 999.0,
            )
        )
        return results

    @staticmethod
    def compute_batch_freshness(batch: Batch) -> BatchFreshnessSummary:
        """Compute overall batch freshness as weighted average of all consumed items' freshness.

        Weight by quantity proportion across all items (already weighted within each item by lots).
        """
        items = FreshnessService.compute_item_freshness_for_batch(batch)
        if not items:
            return BatchFreshnessSummary(
                batch_id=batch.id, overall_freshness_percent=None, items=[]
            )

        total_used_all = sum(i.total_used for i in items)
        if total_used_all <= 0:
            return BatchFreshnessSummary(
                batch_id=batch.id, overall_freshness_percent=None, items=items
            )

        total_weighted_all = 0.0
        for i in items:
            if i.weighted_freshness_percent is not None and i.total_used > 0:
                total_weighted_all += i.weighted_freshness_percent * i.total_used

        overall = (
            round(total_weighted_all / total_used_all, 1)
            if total_weighted_all > 0
            else None
        )
        return BatchFreshnessSummary(
            batch_id=batch.id, overall_freshness_percent=overall, items=items
        )
