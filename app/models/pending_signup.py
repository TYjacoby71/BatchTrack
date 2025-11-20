from __future__ import annotations

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class PendingSignup(db.Model):
    """Tracks Stripe checkout attempts until the organization/user is provisioned."""

    __tablename__ = "pending_signup"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(32), nullable=True)
    signup_source = db.Column(db.String(64), nullable=True)
    referral_code = db.Column(db.String(64), nullable=True)
    promo_code = db.Column(db.String(64), nullable=True)
    detected_timezone = db.Column(db.String(64), nullable=True)

    tier_id = db.Column(
        db.Integer,
        db.ForeignKey("subscription_tier.id"),
        nullable=False,
        index=True,
    )

    oauth_provider = db.Column(db.String(64), nullable=True)
    oauth_provider_id = db.Column(db.String(255), nullable=True)

    extra_metadata = db.Column(db.JSON, nullable=True)

    client_reference_id = db.Column(db.String(255), unique=True, nullable=True)
    stripe_checkout_session_id = db.Column(db.String(255), unique=True, nullable=True)
    stripe_customer_id = db.Column(db.String(255), index=True, nullable=True)

    status = db.Column(db.String(32), nullable=False, default="pending", index=True)
    last_error = db.Column(db.Text, nullable=True)

    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=False,
    )
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships for convenience
    organization = db.relationship(
        "Organization",
        backref=db.backref("pending_signups", lazy="dynamic"),
        lazy="joined",
    )
    user = db.relationship("User", lazy="joined")
    tier = db.relationship("SubscriptionTier", lazy="joined")

    STATUSES = {
        "pending",
        "checkout_created",
        "checkout_completed",
        "account_created",
        "failed",
    }

    def mark_status(self, new_status: str, *, error: str | None = None):
        """Small helper to update status safely."""
        if new_status not in self.STATUSES:
            raise ValueError(f"Invalid pending signup status: {new_status}")
        self.status = new_status
        if new_status == "account_created":
            self.completed_at = TimezoneUtils.utc_now()
        if error:
            self.last_error = error

