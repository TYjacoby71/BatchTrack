from datetime import datetime
from ..extensions import db

class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(64))  # e.g., 'alerts', 'batches', 'inventory'
    required_subscription_tier = db.Column(db.String(32), default='free')  # free, solo, team, enterprise

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to roles
    roles = db.relationship('Role', secondary='role_permission', back_populates='permissions')

    def __repr__(self):
        return f'<Permission {self.name}>'

    @classmethod
    def get_all_permissions(cls):
        """Get all active permissions"""
        return cls.query.filter_by(is_active=True).all()

# Association table for many-to-many relationship
role_permission = db.Table('role_permission',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)