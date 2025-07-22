from app.extensions import db
from datetime import datetime
from flask_login import current_user


class TimestampMixin:
    """Adds created_at and updated_at timestamps to models"""
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ScopedModelMixin:
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)

    @classmethod
    def for_organization(cls, org_id):
        return cls.query.filter_by(organization_id=org_id)

    @classmethod
    def for_current_user(cls):
        """Get records scoped to current user's effective organization (handles developer customer view)"""
        from app.utils.permissions import get_effective_organization_id
        org_id = get_effective_organization_id()
        if org_id:
            return cls.query.filter_by(organization_id=org_id)
        return cls.query.filter(cls.organization_id.is_(None))  # Return empty results if no org

    @classmethod
    def scoped(cls):
        """Return query filtered by current user's organization"""
        if not current_user.is_authenticated:
            return cls.query.filter(False)  # Return empty query if no user

        # Developers can access any organization's data based on session selection
        if current_user.user_type == 'developer':
            from flask import session
            selected_org = session.get('dev_selected_org_id')
            if selected_org:
                return cls.query.filter_by(organization_id=selected_org)
            else:
                return cls.query  # Return all data for developers if no org selected

        # Regular users only see their organization's data
        return cls.query.filter_by(organization_id=current_user.organization_id)

    