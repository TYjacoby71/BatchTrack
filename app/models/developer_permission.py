
from datetime import datetime
from ..extensions import db

class DeveloperPermission(db.Model):
    """Developer/System permissions - completely separate from organization permissions"""
    __tablename__ = 'developer_permission'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(64))  # 'system', 'admin', 'developer'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DeveloperPermission {self.name}>'
    
    @classmethod
    def get_all_active(cls):
        """Get all active developer permissions"""
        return cls.query.filter_by(is_active=True).all()
    
    @classmethod 
    def get_by_category(cls, category):
        """Get permissions by category (system, admin, developer)"""
        return cls.query.filter_by(category=category, is_active=True).all()
