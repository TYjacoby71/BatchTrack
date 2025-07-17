from flask_login import current_user
from ..extensions import db

class ScopedModelMixin:
    """Mixin that adds organization scoping to models"""
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False, index=True)

    @classmethod
    def scoped(cls):
        """Return query filtered by current user's organization"""
        if not current_user.is_authenticated:
            return cls.query.filter(False)  # Return empty query if no user

        # Developers can see all data across organizations
        if current_user.user_type == 'developer':
            return cls.query

        # Regular users see only their organization's data
        return cls.query.filter(cls.organization_id == current_user.organization_id)

    def belongs_to_user(self):
        """Check if this record belongs to the current user's organization"""
        if not current_user.is_authenticated:
            return False
        return self.organization_id == current_user.organization_id