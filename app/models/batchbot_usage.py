from datetime import datetime

from ..extensions import db


class BatchBotUsage(db.Model):
    __tablename__ = "batchbot_usage"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    window_start = db.Column(db.Date, nullable=False, index=True)
    window_end = db.Column(db.Date, nullable=False)
    request_count = db.Column(db.Integer, nullable=False, default=0)
    last_request_at = db.Column(db.DateTime, nullable=True)
    metadata = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "window_start", name="uq_batchbot_usage_org_window"),
    )

    def increment(self, *, delta: int = 1, metadata: dict | None = None) -> None:
        self.request_count = (self.request_count or 0) + max(delta, 0)
        self.last_request_at = datetime.utcnow()
        if metadata:
            self.metadata = {**(self.metadata or {}), **metadata}

    @property
    def remaining(self) -> int | None:
        limit = self.metadata.get("limit") if isinstance(self.metadata, dict) else None
        if limit is None or limit < 0:
            return None
        return max(limit - self.request_count, 0)
