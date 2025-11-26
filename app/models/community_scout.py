from __future__ import annotations

from datetime import timedelta

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


class CommunityScoutBatch(db.Model):
    __tablename__ = 'community_scout_batch'

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(32), nullable=False, default='pending', index=True)
    generated_at = db.Column(db.DateTime, nullable=False, default=TimezoneUtils.utc_now)
    processed_at = db.Column(db.DateTime, nullable=True)
    generated_by_job_id = db.Column(db.String(64), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    claimed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    claimed_at = db.Column(db.DateTime, nullable=True)

    claimed_by_user = db.relationship('User', foreign_keys=[claimed_by_user_id])

    candidates = db.relationship(
        'CommunityScoutCandidate',
        backref='batch',
        lazy=True,
        cascade='all, delete-orphan',
    )

    def mark_completed(self) -> None:
        self.status = 'completed'
        self.processed_at = TimezoneUtils.utc_now()


class CommunityScoutCandidate(db.Model):
    __tablename__ = 'community_scout_candidate'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('community_scout_batch.id'), nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, index=True)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=True, index=True)

    item_snapshot_json = db.Column(db.JSON, nullable=False)
    classification = db.Column(db.String(32), nullable=False, default='unique', index=True)
    match_scores = db.Column(db.JSON, nullable=True)
    sensitivity_flags = db.Column(db.JSON, nullable=True)

    state = db.Column(db.String(32), nullable=False, default='open', index=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_payload = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=TimezoneUtils.utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
    )

    organization = db.relationship('Organization')
    inventory_item = db.relationship('InventoryItem')
    resolver = db.relationship('User', foreign_keys=[resolved_by])

    __table_args__ = (
        db.Index('ix_scout_candidate_org_state', 'organization_id', 'state'),
        db.Index('ix_scout_candidate_class_state', 'classification', 'state'),
    )

    def mark_resolved(self, resolution_payload: dict | None = None, resolved_by_user_id: int | None = None) -> None:
        self.state = 'resolved'
        self.resolved_at = TimezoneUtils.utc_now()
        self.resolution_payload = resolution_payload or {}
        if resolved_by_user_id:
            self.resolved_by = resolved_by_user_id


class CommunityScoutJobState(db.Model):
    __tablename__ = 'community_scout_job_state'

    job_name = db.Column(db.String(64), primary_key=True)
    last_inventory_id_processed = db.Column(db.Integer, nullable=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    lock_owner = db.Column(db.String(64), nullable=True)
    lock_expires_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    def acquire_lock(self, owner: str, ttl_seconds: int = 1800) -> bool:
        now = TimezoneUtils.utc_now()
        if self.lock_expires_at and self.lock_expires_at > now:
            return False
        self.lock_owner = owner
        self.lock_expires_at = now + timedelta(seconds=ttl_seconds)
        return True
