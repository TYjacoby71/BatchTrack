"""Whop authentication service boundary.

Synopsis:
Encapsulates user/org lookup + persistence for Whop login flows so auth helper
code avoids direct model queries and commits.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import User


class WhopAuthService:
    """Service helpers for Whop auth user/org persistence paths."""

    @staticmethod
    def find_user_by_email(email: str) -> User | None:
        return User.find_by_email(email)

    @staticmethod
    def ensure_unique_username(base_username: str) -> str:
        candidate = base_username
        counter = 1
        while User.username_exists(candidate):
            candidate = f"{base_username}{counter}"
            counter += 1
        return candidate

    @staticmethod
    def attach_user_to_organization(user: User, organization_id: int) -> None:
        user.organization_id = organization_id
        db.session.commit()

    @staticmethod
    def create_user_for_organization(
        *,
        email: str,
        username: str,
        organization_id: int,
    ) -> User:
        user = User(
            email=email,
            username=username,
            organization_id=organization_id,
            is_active=True,
        )
        db.session.add(user)
        db.session.commit()
        return user
