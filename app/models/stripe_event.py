from app.extensions import db
from app.utils.timezone_utils import TimezoneUtils


class StripeEvent(db.Model):
    """Model to track Stripe webhook events for idempotency"""

    __tablename__ = "stripe_event"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(128), nullable=False)
    received_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(32), default="received")  # received, processed, failed
    error_message = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<StripeEvent {self.event_id} ({self.event_type})>"
