from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class BatchBotCreditBundle(db.Model):
    __tablename__ = "batchbot_credit_bundle"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True
    )
    addon_id = db.Column(db.Integer, db.ForeignKey("addon.id"), nullable=True)
    source = db.Column(
        db.String(64), nullable=False, default="manual"
    )  # manual | addon | promo
    reference = db.Column(db.String(128), nullable=True)
    purchased_requests = db.Column(db.Integer, nullable=False, default=0)
    remaining_requests = db.Column(db.Integer, nullable=False, default=0)
    details = db.Column(db.JSON, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=TimezoneUtils.utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
    )

    addon = db.relationship("Addon", lazy="joined")
