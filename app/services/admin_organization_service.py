"""Admin organization service boundary.

Synopsis:
Encapsulates admin-only organization and user lookup operations so admin
blueprint routes avoid direct persistence access.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Organization, User


class AdminOrganizationService:
    """Service helpers for admin organization views."""

    @staticmethod
    def list_organizations() -> list[Organization]:
        return Organization.query.all()

    @staticmethod
    def get_organization_or_404(org_id: int) -> Organization:
        return db.get_or_404(Organization, org_id)

    @staticmethod
    def list_users_for_organization(org_id: int) -> list[User]:
        return User.query.filter_by(organization_id=org_id).all()
