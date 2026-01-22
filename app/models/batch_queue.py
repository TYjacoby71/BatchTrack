from __future__ import annotations

from ..extensions import db
from .mixins import ScopedModelMixin
from ..utils.timezone_utils import TimezoneUtils


class BatchQueueItem(ScopedModelMixin, db.Model):
    __tablename__ = 'batch_queue_item'

    id = db.Column(db.Integer, primary_key=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)

    queue_code = db.Column(db.String(32), nullable=False, index=True)
    queue_position = db.Column(db.Integer, nullable=False, default=0)

    scale = db.Column(db.Float, nullable=False, default=1.0)
    batch_type = db.Column(db.String(32), nullable=False, default='ingredient')
    projected_yield = db.Column(db.Float, nullable=True)
    projected_yield_unit = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    plan_snapshot = db.Column(db.JSON, nullable=True)

    status = db.Column(db.String(32), nullable=False, default='queued')  # queued, started, cancelled

    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=False, index=True)
    started_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)

    recipe = db.relationship('Recipe')
    batch = db.relationship('Batch')
    creator = db.relationship('User', foreign_keys=[created_by])
    organization = db.relationship('Organization', foreign_keys=[organization_id])

    __table_args__ = (
        db.Index('ix_batch_queue_org_status_created', 'organization_id', 'status', 'created_at'),
    )

    def __repr__(self):
        return f'<BatchQueueItem {self.id} | {self.queue_code} | {self.status}>'
