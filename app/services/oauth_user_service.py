"""OAuth user persistence service boundary.

Synopsis:
Encapsulates OAuth-related user lookup and persistence operations so auth route
handlers avoid direct query/session usage for these paths.
"""

from __future__ import annotations

from app.extensions import db
from app.models import User
from app.utils.timezone_utils import TimezoneUtils


class OAuthUserService:
    """Service helpers for OAuth user lookup and update flows."""

    @staticmethod
    def find_user_by_email(email: str) -> User | None:
        return User.find_by_email(email)

    @staticmethod
    def ensure_oauth_identity(
        *,
        user: User,
        provider: str,
        oauth_id: str | None,
    ) -> None:
        if user.oauth_provider:
            return
        user.oauth_provider = provider
        user.oauth_provider_id = oauth_id
        user.email_verified = True
        db.session.commit()

    @staticmethod
    def update_last_login(user: User) -> None:
        user.last_login = TimezoneUtils.utc_now()
        db.session.commit()

    @staticmethod
    def update_last_login_to_now(user: User) -> None:
        """Alias for explicit timestamped login updates in auth routes."""
        OAuthUserService.update_last_login(user)
