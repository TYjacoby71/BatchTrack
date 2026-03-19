"""Marketing lead contact and event models.

Synopsis:
Stores canonical contact rows and source-tagged capture events for waitlists and
other marketing email collection flows.

Glossary:
- Contact: Unique person identified by normalized email.
- Capture event: A single source-tagged marketing lead ingestion record.
"""

from __future__ import annotations

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class MarketingContact(db.Model):
    """Canonical marketing contact keyed by normalized email address."""

    __tablename__ = "marketing_contact"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False)
    email_normalized = db.Column(
        db.String(255), nullable=False, unique=True, index=True
    )
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    business_type = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    traits_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    events = db.relationship(
        "MarketingLeadEvent",
        back_populates="contact",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<MarketingContact {self.email_normalized}>"


class MarketingLeadEvent(db.Model):
    """Source-tagged marketing lead capture event."""

    __tablename__ = "marketing_lead_event"

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(
        db.Integer, db.ForeignKey("marketing_contact.id"), nullable=False, index=True
    )
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=True, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    event_type = db.Column(db.String(64), nullable=False, index=True)
    source_key = db.Column(db.String(128), nullable=True, index=True)
    waitlist_key = db.Column(db.String(128), nullable=True, index=True)
    context = db.Column(db.String(128), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    tags_json = db.Column(db.JSON, nullable=True)
    payload_json = db.Column(db.JSON, nullable=True)
    occurred_at = db.Column(
        db.DateTime, default=TimezoneUtils.utc_now, nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )

    contact = db.relationship("MarketingContact", back_populates="events")
    organization = db.relationship("Organization")
    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<MarketingLeadEvent {self.event_type} {self.id}>"
