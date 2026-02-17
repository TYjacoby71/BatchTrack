from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Permission, Role

__all__ = ["update_organization_owner_permissions", "assign_organization_owner_role"]

logger = logging.getLogger(__name__)
_OWNER_ROLE_NAME = "organization_owner"


def _get_owner_role() -> Optional[Role]:
    return Role.query.filter_by(name=_OWNER_ROLE_NAME, is_system_role=True).first()


def update_organization_owner_permissions(*, auto_commit: bool = True) -> bool:
    """
    Ensure the organization owner system role stays in sync with active permissions.

    Args:
        auto_commit: When True (default) the session is committed after the update.
    """
    try:
        role = _get_owner_role()
        if role is None:
            logger.warning(
                "Organization owner system role not found; cannot sync permissions."
            )
            return False

        active_permissions = Permission.query.filter_by(is_active=True).all()
        role.permissions = active_permissions
        if auto_commit:
            db.session.commit()

        logger.info(
            "Synchronized organization owner role with %d active permissions.",
            len(active_permissions),
        )
        return True

    except SQLAlchemyError as exc:
        logger.error("Failed to sync organization owner permissions: %s", exc)
        db.session.rollback()
        return False


def assign_organization_owner_role(user, *, auto_commit: bool = False) -> bool:
    """
    Attach the organization owner role to the provided user.

    Args:
        user: User instance receiving the role.
        auto_commit: Commit immediately after assignment (defaults to False to
                     preserve legacy behavior).
    """
    if user is None:
        logger.warning("assign_organization_owner_role called without a user.")
        return False

    try:
        role = _get_owner_role()
        if role is None:
            logger.warning(
                "Organization owner system role not found; cannot assign to user %s.",
                user,
            )
            return False

        user.assign_role(role)
        if auto_commit:
            db.session.commit()

        logger.info(
            "Assigned organization owner role to user %s.", getattr(user, "id", user)
        )
        return True

    except SQLAlchemyError as exc:
        logger.error("Failed to assign organization owner role: %s", exc)
        db.session.rollback()
        return False
