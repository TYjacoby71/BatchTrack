from datetime import datetime
from ..extensions import db


class RetentionDeletionQueue(db.Model):
    __tablename__ = 'retention_deletion_queue'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('recipe.id'), nullable=False)

    # Status lifecycle: pending -> queued -> deleted | canceled
    status = db.Column(db.String(16), default='pending', nullable=False)

    # When user acknowledged the drawer for this item
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    # When this item becomes eligible for hard deletion (retention + 15d, or ack + up to 15d cap)
    delete_after_at = db.Column(db.DateTime, nullable=True)

    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    recipe = db.relationship('Recipe')

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'recipe_id', name='uq_retention_queue_org_recipe'),
    )

