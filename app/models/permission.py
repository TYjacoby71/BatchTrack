from datetime import datetime
from ..extensions import db

class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(64))  # e.g., 'alerts', 'batches', 'inventory'
    required_subscription_tier = db.Column(db.String(32), default='free')  # Minimum tier required
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to roles
    roles = db.relationship('Role', secondary='role_permission', back_populates='permissions')

    def __repr__(self):
        return f'<Permission {self.name}>'

    def is_available_for_tier(self, subscription_tier):
        """Check if permission is available for given subscription tier"""
        tier_hierarchy = {
            'free': 0,
            'solo': 1,
            'team': 2,
            'enterprise': 3
        }

        required_level = tier_hierarchy.get(self.required_subscription_tier, 0)
        current_level = tier_hierarchy.get(subscription_tier, 0)

        return current_level >= required_level

    @classmethod
    def get_permissions_for_tier(cls, subscription_tier):
        """Get all permissions available for a subscription tier"""
        return [perm for perm in cls.query.filter_by(is_active=True).all() 
                if perm.is_available_for_tier(subscription_tier)]

    @classmethod
    def get_organization_permissions(cls):
        """Get all organization permissions (all permissions in this table are organization permissions)"""
        return cls.query.filter_by(is_active=True).all()

# Association table for many-to-many relationship
role_permission = db.Table('role_permission',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)