"""Drawer route resolution service boundary.

Synopsis:
Encapsulates organization/user scoped lookups used by drawer endpoints so
route handlers avoid direct session/model access for common resolution paths.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Organization
from app.models.unit import CustomUnitMapping


class DrawerResolutionService:
    """Service helpers for common drawer route lookups."""

    @staticmethod
    def resolve_current_user_organization(
        *, organization_id: int | None
    ) -> Organization | None:
        if not organization_id:
            return None
        return Organization.query.filter_by(id=organization_id).first()

    @staticmethod
    def get_organization(org_id: int | None) -> Organization | None:
        if not org_id:
            return None
        return db.session.get(Organization, org_id)

    @staticmethod
    def upsert_custom_unit_mapping(
        *,
        organization_id: int | None,
        from_unit: str,
        to_unit: str,
        conversion_factor: float,
    ) -> bool:
        existing = (
            CustomUnitMapping.scoped()
            .filter_by(
                from_unit=from_unit,
                to_unit=to_unit,
                organization_id=organization_id,
            )
            .first()
        )
        if existing:
            existing.conversion_factor = conversion_factor
            created = False
        else:
            mapping = CustomUnitMapping(
                from_unit=from_unit,
                to_unit=to_unit,
                conversion_factor=conversion_factor,
                organization_id=organization_id,
            )
            db.session.add(mapping)
            created = True
        db.session.commit()
        return created
