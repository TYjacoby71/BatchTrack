from datetime import datetime, timezone
from ..extensions import db
from .mixins import ScopedModelMixin

class UserPreferences(ScopedModelMixin, db.Model):
    """Store individual user preferences for alerts and display settings"""
    __tablename__ = 'user_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    # Appearance
    # Theme preference: 'system' (follow OS), 'light', 'dark', 'warm', etc.
    theme = db.Column(db.String(20), nullable=True)

    # Alert preferences
    max_dashboard_alerts = db.Column(db.Integer, default=3)
    show_expiration_alerts = db.Column(db.Boolean, default=True)
    show_timer_alerts = db.Column(db.Boolean, default=True)
    show_low_stock_alerts = db.Column(db.Boolean, default=True)
    show_batch_alerts = db.Column(db.Boolean, default=True)
    show_fault_alerts = db.Column(db.Boolean, default=True)
    show_alert_badges = db.Column(db.Boolean, default=True)

    # Display preferences
    dashboard_layout = db.Column(db.String(32), default='standard')
    compact_view = db.Column(db.Boolean, default=False)
    show_quick_actions = db.Column(db.Boolean, default=True)

    # Timezone preferences (mirrors user.timezone for easy access)
    timezone = db.Column(db.String(64), default='America/New_York')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship
    user = db.relationship('User', backref='preferences')

    @classmethod
    def get_for_user(cls, user_id):
        """Get or create user preferences for a user"""
        from . import User
        user = User.query.get(user_id)
        if not user:
            return None

        # Check if preferences already exist
        preferences = cls.query.filter_by(user_id=user_id).first()
        if not preferences:
            # For developers, use a default organization_id or skip preferences creation
            if user.user_type == 'developer':
                # Developers don't need user preferences since they work across organizations
                return None

            # Create default preferences for regular users
            if not user.organization_id:
                # If user has no organization, can't create preferences
                return None

            preferences = cls(
                user_id=user_id,
                organization_id=user.organization_id
            )
            db.session.add(preferences)
            db.session.commit()

        return preferences