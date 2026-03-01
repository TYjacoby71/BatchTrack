import logging
from datetime import date, datetime
from typing import Optional

from app.models import FreshnessSnapshot, InventoryItem, UnifiedInventoryHistory, db

logger = logging.getLogger(__name__)



class FreshnessSnapshotService:
    @staticmethod
    def compute_for_item(
        inventory_item_id: int, snapshot_date: date
    ) -> Optional[FreshnessSnapshot]:
        """Compute freshness metrics for a single item for the given date.
        Uses events up to end-of-day snapshot_date.
        """
        item = db.session.get(InventoryItem, inventory_item_id)
        if not item:
            return None

        day_end = datetime.combine(snapshot_date, datetime.max.time())

        # Query recent movement events for this item up to the snapshot date
        events = UnifiedInventoryHistory.query.filter(
            UnifiedInventoryHistory.inventory_item_id == inventory_item_id,
            UnifiedInventoryHistory.timestamp <= day_end,
        ).all()

        def age_days(e):
            try:
                if e.affected_lot and e.affected_lot.received_date and e.timestamp:
                    return max(0, (e.timestamp - e.affected_lot.received_date).days)
            except Exception:
                logger.warning("Suppressed exception fallback at app/services/freshness_snapshot_service.py:31", exc_info=True)
                return None
            return None

        spoilage_events = [
            ev
            for ev in events
            if ev.change_type in ["spoil", "expired", "damaged", "trash"]
        ]
        usage_events = [
            ev for ev in events if ev.change_type in ["use", "production", "batch"]
        ]

        spoilage_days = [
            d for d in (age_days(ev) for ev in spoilage_events) if d is not None
        ]
        usage_days = [d for d in (age_days(ev) for ev in usage_events) if d is not None]

        avg_days_to_spoilage = (
            (sum(spoilage_days) / len(spoilage_days)) if spoilage_days else None
        )
        avg_days_to_usage = (sum(usage_days) / len(usage_days)) if usage_days else None

        total_events = len(spoilage_events) + len(usage_events)
        freshness_efficiency_score = (
            (len(usage_events) / total_events * 100.0) if total_events > 0 else None
        )

        # Upsert snapshot row
        snap = FreshnessSnapshot.query.filter_by(
            snapshot_date=snapshot_date,
            organization_id=item.organization_id,
            inventory_item_id=item.id,
        ).first()

        if not snap:
            snap = FreshnessSnapshot(
                snapshot_date=snapshot_date,
                organization_id=item.organization_id,
                inventory_item_id=item.id,
            )
            db.session.add(snap)

        snap.avg_days_to_usage = avg_days_to_usage
        snap.avg_days_to_spoilage = avg_days_to_spoilage
        snap.freshness_efficiency_score = freshness_efficiency_score
        db.session.commit()

        return snap

    @staticmethod
    def compute_for_org(organization_id: int, snapshot_date: date) -> int:
        """Compute snapshots for all items in an organization. Returns count."""
        items = InventoryItem.query.filter_by(organization_id=organization_id).all()
        count = 0
        for item in items:
            if FreshnessSnapshotService.compute_for_item(item.id, snapshot_date):
                count += 1
        return count

    @staticmethod
    def compute_for_all(snapshot_date: date) -> int:
        """Compute snapshots for all organizations on a date. Returns total count."""
        from app.models import Organization

        orgs = Organization.query.all()
        total = 0
        for org in orgs:
            total += FreshnessSnapshotService.compute_for_org(org.id, snapshot_date)
        return total
