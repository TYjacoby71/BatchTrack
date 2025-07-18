from flask_login import current_user
from ..extensions import db

class ScopedModelMixin:
    """Mixin to automatically scope queries to the current user's organization"""

    @classmethod
    def scoped(cls):
        """Return a query scoped to the current user's organization"""
        from flask_login import current_user
        from flask import session

        # For developers, check if they've selected an organization to view
        if hasattr(current_user, 'user_type') and current_user.user_type == 'developer':
            selected_org_id = session.get('dev_selected_org_id')
            if selected_org_id:
                return cls.query.filter_by(organization_id=selected_org_id)
            else:
                # If no organization selected, return all (for developer overview)
                return cls.query

        # For regular users, scope to their organization
        if hasattr(current_user, 'organization_id') and current_user.organization_id:
            return cls.query.filter_by(organization_id=current_user.organization_id)
        return cls.query.filter(False)  # Return empty query if no organization