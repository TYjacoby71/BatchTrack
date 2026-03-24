"""App dashboard service boundary.

Synopsis:
Encapsulates dashboard route data access and transaction reset helpers so
dashboard controllers remain transport-focused.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Batch, Organization


class AppDashboardService:
    """Service helpers for app dashboard routes."""

    @staticmethod
    def get_selected_organization(selected_org_id: int | None) -> Organization | None:
        if not selected_org_id:
            return None
        return db.session.get(Organization, selected_org_id)

    @staticmethod
    def organization_exists(selected_org_id: int | None) -> bool:
        return AppDashboardService.get_selected_organization(selected_org_id) is not None

    @staticmethod
    def get_active_in_progress_batch(
        organization_id: int | None,
    ) -> Batch | None:
        query = Batch.scoped().filter_by(status="in_progress")
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        return query.first()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
