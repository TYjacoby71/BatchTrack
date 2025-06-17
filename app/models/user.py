
from datetime import datetime
from flask_login import UserMixin
from ..extensions import db

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    subscription_tier = db.Column(db.String(32), default='free')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    users = db.relationship('User', backref='organization')
    
    @property
    def active_users_count(self):
        return len([u for u in self.users if u.is_active])
    
    @property
    def owner(self):
        """Get the organization owner (first created user)"""
        return User.query.filter_by(organization_id=self.id).order_by(User.created_at).first()
    
    def can_add_users(self):
        """Check if organization can add more users based on subscription"""
        if self.subscription_tier == 'free':
            return self.active_users_count < 1  # Solo only
        elif self.subscription_tier == 'team':
            return self.active_users_count < 10  # Up to 10 users
        else:
            return True  # Unlimited for enterprise

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), default='user')
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    subscription_class = db.Column(db.String(32), default='free')
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)
    
    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.username
    
    @property
    def is_organization_owner(self):
        """Check if user is the owner of their organization"""
        first_user = User.query.filter_by(organization_id=self.organization_id).order_by(User.created_at).first()
        return first_user and first_user.id == self.id
