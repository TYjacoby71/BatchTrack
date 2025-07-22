
from datetime import datetime
from ..extensions import db

# Association table for developer roles and permissions
developer_role_permission = db.Table('developer_role_permission',
    db.Column('developer_role_id', db.Integer, db.ForeignKey('developer_role.id'), primary_key=True),
    db.Column('developer_permission_id', db.Integer, db.ForeignKey('developer_permission.id'), primary_key=True)
)

class DeveloperRole(db.Model):
    """Developer/System roles - completely separate from organization roles"""
    __tablename__ = 'developer_role'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(32), default='developer')  # 'developer', 'admin', 'system'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to developer permissions
    permissions = db.relationship('DeveloperPermission', 
                                secondary=developer_role_permission, 
                                backref='developer_roles')
    
    def __repr__(self):
        return f'<DeveloperRole {self.name}>'
    
    def has_permission(self, permission_name):
        """Check if this developer role has a specific permission"""
        return any(perm.name == permission_name for perm in self.permissions if perm.is_active)
    
    def get_permissions(self):
        """Get all active permissions for this developer role"""
        return [perm for perm in self.permissions if perm.is_active]
    
    @classmethod
    def get_by_category(cls, category):
        """Get roles by category"""
        return cls.query.filter_by(category=category, is_active=True).all()
