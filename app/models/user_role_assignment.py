
from datetime import datetime
from ..extensions import db
from .mixins import ScopedModelMixin

class UserRoleAssignment(ScopedModelMixin, db.Model):
    """Many-to-many relationship between users and roles with assignment tracking"""
    __tablename__ = 'user_role_assignment'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    
    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='role_assignments')
    role = db.relationship('Role', backref='user_assignments')
    assigner = db.relationship('User', foreign_keys=[assigned_by])
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'role_id', 'organization_id', name='unique_user_role_org'),
    )
