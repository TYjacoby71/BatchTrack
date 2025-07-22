from datetime import datetime
from ..extensions import db
from .mixins import ScopedModelMixin

class UserRoleAssignment(db.Model):
    __tablename__ = 'user_role_assignment'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=True)  # Organization role
    developer_role_id = db.Column(db.Integer, db.ForeignKey('developer_role.id'), nullable=True)  # Developer role
    
    # Add constraint to ensure either role_id OR developer_role_id is set, but not both
    __table_args__ = (
        db.CheckConstraint(
            '(role_id IS NOT NULL AND developer_role_id IS NULL) OR (role_id IS NULL AND developer_role_id IS NOT NULL)',
            name='check_exactly_one_role'
        ),
    )
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    # Relationships
    user = db.relationship('User', foreign_keys=[user_id], backref='role_assignments')
    role = db.relationship('Role', backref='user_assignments')  # Organization role
    developer_role = db.relationship('DeveloperRole', backref='user_assignments')  # Developer role
    assigner = db.relationship('User', foreign_keys=[assigned_by])
    organization = db.relationship('Organization')

    @property
    def active_role(self):
        """Get the active role (either organization or developer role)"""
        if self.developer_role_id:
            return self.developer_role
        return self.role