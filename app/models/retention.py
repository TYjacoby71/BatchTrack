from datetime import datetime, timezone

from ..extensions import db


class RetentionDeletionQueue(db.Model):
    __tablename__ = "retention_deletion_queue"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False
    )
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipe.id"), nullable=False)

    # Status lifecycle: pending -> queued -> deleted | canceled
    status = db.Column(db.String(16), default="pending", nullable=False)

    # When user acknowledged the drawer for this item
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    # When this item becomes eligible for hard deletion (retention + 15d, or ack + up to 15d cap)
    delete_after_at = db.Column(db.DateTime, nullable=True)

    # Audit
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    recipe = db.relationship("Recipe")

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "recipe_id", name="uq_retention_queue_org_recipe"
        ),
    )


class StorageAddonPurchase(db.Model):
    __tablename__ = "storage_addon_purchase"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False
    )
    stripe_session_id = db.Column(db.String(255), nullable=True)
    stripe_price_lookup_key = db.Column(db.String(128), nullable=True)
    retention_extension_days = db.Column(db.Integer, default=0)
    purchased_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    organization = db.relationship("Organization")


class StorageAddonSubscription(db.Model):
    __tablename__ = "storage_addon_subscription"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False
    )
    stripe_subscription_id = db.Column(db.String(255), nullable=False, unique=True)
    price_lookup_key = db.Column(db.String(128), nullable=True)
    status = db.Column(
        db.String(32), nullable=False, default="active"
    )  # active, trialing, past_due, canceled
    current_period_end = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    organization = db.relationship("Organization")
