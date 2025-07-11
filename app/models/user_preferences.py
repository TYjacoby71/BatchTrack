
from datetime import datetime
from ..extensions import db
from .mixins import ScopedModelMixin

class UserPreferences(ScopedModelMixin, db.Model):
    """Store individual user preferences for alerts and display settings"""
    __tablename__ = 'user_preferences'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    
    # Alert preferences
    max_dashboard_alerts = db.Column(db.Integer, default=3)
    show_expiration_alerts = db.Column(db.Boolean, default=True)
    show_timer_alerts = db.Column(db.Boolean, default=True)
    show_low_stock_alerts = db.Column(db.Boolean, default=True)
    show_batch_alerts = db.Column(db.Boolean, default=True)
    show_fault_alerts = db.Column(db.Boolean, default=True)
    expiration_warning_days = db.Column(db.Integer, default=3)
    show_alert_badges = db.Column(db.Boolean, default=True)
    
    # Display preferences
    dashboard_layout = db.Column(db.String(32), default='standard')
    compact_view = db.Column(db.Boolean, default=False)
    show_quick_actions = db.Column(db.Boolean, default=True)
    
    # Timezone preferences (mirrors user.timezone for easy access)
    timezone = db.Column(db.String(64), default='America/New_York')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    user = db.relationship('User', backref='preferences')
    
    @classmethod
    def get_for_user(cls, user_id):
        """Get or create preferences for a user"""
        prefs = cls.query.filter_by(user_id=user_id).first()
        if not prefs:
            # Get the user to access their organization_id
            from .models import User
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            prefs = cls(user_id=user_id, organization_id=user.organization_id)
            db.session.add(prefs)
            db.session.commit()
        return prefs
