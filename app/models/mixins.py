from app.extensions import db
from datetime import datetime
from flask_login import current_user


class TimestampMixin:
    """Adds created_at and updated_at timestamps to models"""
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ScopedModelMixin:
    """Adds organization scoping to models"""
    organization_id = db.Column(db.Integer, 
                               db.ForeignKey('organization.id'), 
                               nullable=False)

    @classmethod
    def for_organization(cls, org_id):
        """Get all records for a specific organization"""
        return cls.query.filter_by(organization_id=org_id)

    @classmethod
    def for_current_user(cls):
        """Get records for current user's organization"""
        if current_user and current_user.is_authenticated:
            if current_user.user_type == 'developer':
                # Developers need to select organization context
                from flask import session
                selected_org = session.get('dev_selected_org_id')
                if selected_org:
                    return cls.for_organization(selected_org)
                else:
                    return cls.query.filter(False)  # Return empty query
            else:
                return cls.for_organization(current_user.organization_id)
        return cls.query.filter(False)  # Return empty query if no user