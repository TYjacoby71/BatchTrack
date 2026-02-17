from datetime import datetime, timezone

from ..extensions import db
from .mixins import ScopedModelMixin


class FreshnessSnapshot(ScopedModelMixin, db.Model):
    """Daily freshness metrics per inventory item (org-scoped)."""

    __tablename__ = "freshness_snapshot"

    id = db.Column(db.Integer, primary_key=True)
    snapshot_date = db.Column(db.Date, nullable=False, index=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True
    )
    inventory_item_id = db.Column(
        db.Integer, db.ForeignKey("inventory_item.id"), nullable=False, index=True
    )

    # Metrics
    avg_days_to_usage = db.Column(db.Float, nullable=True)
    avg_days_to_spoilage = db.Column(db.Float, nullable=True)
    freshness_efficiency_score = db.Column(db.Float, nullable=True)  # 0-100

    # Audit
    computed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = db.relationship("Organization")
    inventory_item = db.relationship("InventoryItem")

    __table_args__ = (
        db.UniqueConstraint(
            "snapshot_date",
            "organization_id",
            "inventory_item_id",
            name="uq_freshness_snapshot_unique",
        ),
    )
