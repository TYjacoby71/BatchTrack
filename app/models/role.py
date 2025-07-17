
from datetime import datetime
from ..extensions import db
from .mixins import ScopedModelMixin

class Role(ScopedModelMixin, db.Model):
    __tablename__ = 'role'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    is_system_role = db.Column(db.Boolean, default=False)  # System roles cannot be deleted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=True)
    
    # Relationship to permissions
    permissions = db.relationship('Permission', secondary='role_permission', back_populates='roles')
    
    __table_args__ = (
        db.UniqueConstraint('name', 'organization_id', name='unique_role_name_org'),
    )
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    def has_permission(self, permission_name):
        """Check if this role has a specific permission"""
        return any(perm.name == permission_name for perm in self.permissions if perm.is_active)
    
    def get_permissions(self):
        """Get all active permissions for this role"""
        return [perm for perm in self.permissions if perm.is_active]
    
    @classmethod
    def get_system_roles(cls):
        """Get all system roles"""
        return cls.query.filter_by(is_system_role=True).all()
    
    @classmethod
    def get_organization_roles(cls, organization_id):
        """Get roles for a specific organization (custom + system)"""
        return cls.query.filter(
            (cls.organization_id == organization_id) | 
            (cls.is_system_role == True)
        ).filter_by(is_active=True).all()
