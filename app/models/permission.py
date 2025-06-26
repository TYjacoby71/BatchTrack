
from ..extensions import db

class Permission(db.Model):
    __tablename__ = 'permission'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(64))  # e.g., 'alerts', 'batches', 'inventory'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationship to roles
    roles = db.relationship('Role', secondary='role_permission', back_populates='permissions')
    
    def __repr__(self):
        return f'<Permission {self.name}>'

# Association table for many-to-many relationship
role_permission = db.Table('role_permission',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id'), primary_key=True)
)
