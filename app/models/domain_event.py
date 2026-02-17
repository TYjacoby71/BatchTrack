from datetime import datetime, timezone

from ..extensions import db
from .mixins import ScopedModelMixin


class DomainEvent(ScopedModelMixin, db.Model):
    """Generic domain event for analytics and outbox-style processing."""

    __tablename__ = "domain_event"

    id = db.Column(db.Integer, primary_key=True)
    event_name = db.Column(db.String(128), nullable=False, index=True)
    occurred_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Actor and tenant context
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=True, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)

    # Entity context
    entity_type = db.Column(db.String(64), nullable=True, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)

    # Optional correlation and source info
    correlation_id = db.Column(db.String(128), nullable=True, index=True)
    source = db.Column(db.String(64), nullable=True, default="app")
    schema_version = db.Column(db.Integer, nullable=True, default=1)

    # Event payload
    properties = db.Column(db.JSON, nullable=True)

    # Outbox processing fields (for async delivery if needed)
    is_processed = db.Column(db.Boolean, default=False, index=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    delivery_attempts = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = db.relationship("Organization")
    user = db.relationship("User")

    def __repr__(self):
        return f"<DomainEvent {self.event_name} {self.id}>"
