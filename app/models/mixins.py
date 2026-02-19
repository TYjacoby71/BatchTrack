from flask import session
from flask_login import current_user

from app.extensions import db


class OrganizationScopedMixin:
    """Mixin to automatically scope queries by organization"""

    @classmethod
    def scoped(cls, organization_id=None):
        """Return query scoped to organization"""
        if organization_id is None:
            # Simple organization scoping
            if current_user.is_authenticated:
                if current_user.user_type == "developer":
                    organization_id = session.get("dev_selected_org_id")
                else:
                    organization_id = current_user.organization_id

        if organization_id:
            return cls.query.filter_by(organization_id=organization_id)
        else:
            # For developers not in customer view, return all
            if current_user.is_authenticated and current_user.user_type == "developer":
                return cls.query
            else:
                # No organization context - return empty query
                return cls.query.filter(False)

    @classmethod
    def for_organization(cls, organization_id):
        """Explicitly scope to specific organization"""
        return cls.query.filter_by(organization_id=organization_id)

    def ensure_organization_scope(self):
        """Ensure this record belongs to current user's organization"""
        if current_user.user_type == "developer":
            return True  # Developers can access all

        effective_org_id = (
            session.get("dev_selected_org_id")
            if current_user.user_type == "developer"
            else current_user.organization_id
        )
        return self.organization_id == effective_org_id


class PermissionRequiredMixin:
    """Mixin to enforce permissions on model operations"""

    # Override these in your models
    CREATE_PERMISSION = None
    UPDATE_PERMISSION = None
    DELETE_PERMISSION = None
    VIEW_PERMISSION = None

    def can_create(self):
        """Check if current user can create this type of record"""
        if self.CREATE_PERMISSION:
            from app.utils.permissions import has_permission

            return has_permission(self.CREATE_PERMISSION)
        return True

    def can_update(self):
        """Check if current user can update this record"""
        if self.UPDATE_PERMISSION:
            from app.utils.permissions import has_permission

            return (
                has_permission(self.UPDATE_PERMISSION)
                and self.ensure_organization_scope()
            )
        return self.ensure_organization_scope()

    def can_delete(self):
        """Check if current user can delete this record"""
        if self.DELETE_PERMISSION:
            from app.utils.permissions import has_permission

            return (
                has_permission(self.DELETE_PERMISSION)
                and self.ensure_organization_scope()
            )
        return self.ensure_organization_scope()

    def can_view(self):
        """Check if current user can view this record"""
        if self.VIEW_PERMISSION:
            from app.utils.permissions import has_permission

            return (
                has_permission(self.VIEW_PERMISSION)
                and self.ensure_organization_scope()
            )
        return self.ensure_organization_scope()


class TimestampMixin:
    """Adds created_at and updated_at timestamps to models"""

    from ..utils.timezone_utils import TimezoneUtils

    created_at = db.Column(db.DateTime, default=TimezoneUtils.utc_now, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=TimezoneUtils.utc_now,
        onupdate=TimezoneUtils.utc_now,
        nullable=True,
    )


class ScopedModelMixin:
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=True
    )

    @classmethod
    def for_organization(cls, org_id):
        return cls.query.filter_by(organization_id=org_id)

    @classmethod
    def for_current_user(cls):
        """Get records scoped to current user's organization"""
        from flask import session
        from flask_login import current_user

        if not current_user.is_authenticated:
            return cls.query.filter(False)

        # For developers in customer view mode
        if current_user.user_type == "developer":
            org_id = session.get("dev_selected_org_id")
        else:
            org_id = current_user.organization_id

        if org_id:
            return cls.query.filter_by(organization_id=org_id)
        return cls.query.filter(False)  # Return empty results if no org

    @classmethod
    def scoped(cls):
        """Return query filtered by current user's organization"""
        from flask import session
        from flask_login import current_user

        if not current_user.is_authenticated:
            return cls.query.filter(False)  # Return empty query if no user

        # Simple organization scoping without complex effective logic
        if current_user.user_type == "developer":
            org_id = session.get("dev_selected_org_id")
        else:
            org_id = current_user.organization_id

        if org_id:
            return cls.query.filter_by(organization_id=org_id)
        else:
            # No organization context - return empty for safety
            return cls.query.filter(False)
