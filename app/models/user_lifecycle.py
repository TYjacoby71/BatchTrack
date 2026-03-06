"""User model lifecycle hooks.

Synopsis:
Contains SQLAlchemy lifecycle listeners for `User` creation side effects.
Keeps model event wiring out of `models.py` for clearer separation.
"""

from __future__ import annotations

import logging

from flask import has_app_context
from sqlalchemy import event

from ..utils.timezone_utils import TimezoneUtils
from .models import User

logger = logging.getLogger(__name__)


# --- User verification defaults hook ---
# Purpose: Initialize verification state for newly-created user accounts.
@event.listens_for(User, "before_insert")
def _prepare_user_verification_before_insert(mapper, connection, target):
    if not getattr(target, "email", None):
        return
    if bool(getattr(target, "email_verified", False)):
        return
    if not has_app_context():
        return

    try:
        from ..services.email_service import EmailService

        if not EmailService.should_issue_verification_tokens():
            target.email_verification_token = None
            target.email_verification_sent_at = None
            return

        if not getattr(target, "email_verification_token", None):
            target.email_verification_token = EmailService.generate_verification_token(
                target.email
            )
        if not getattr(target, "email_verification_sent_at", None):
            target.email_verification_sent_at = TimezoneUtils.utc_now()
    except Exception as exc:
        logger.warning(
            "Unable to prepare verification defaults for new user %s: %s",
            getattr(target, "email", None),
            exc,
        )


# --- User verification send hook ---
# Purpose: Send verification email whenever a new unverified user is created.
@event.listens_for(User, "after_insert")
def _send_verification_after_user_insert(mapper, connection, target):
    if not getattr(target, "email", None):
        return
    if bool(getattr(target, "email_verified", False)):
        return
    token = getattr(target, "email_verification_token", None)
    if not token:
        return
    if not has_app_context():
        return

    sent = False
    try:
        from ..services.email_service import EmailService

        sent = EmailService.send_verification_email(
            target.email,
            token,
            getattr(target, "first_name", None) or getattr(target, "username", None),
        )
    except Exception as exc:
        logger.warning(
            "Automatic verification send failed for new user %s: %s",
            getattr(target, "id", None),
            exc,
        )

    if sent:
        return

    try:
        user_table = User.__table__
        connection.execute(
            user_table.update()
            .where(user_table.c.id == target.id)
            .values(email_verification_token=None, email_verification_sent_at=None)
        )
    except Exception as clear_exc:
        logger.warning(
            "Failed to clear verification cooldown fields for new user %s: %s",
            getattr(target, "id", None),
            clear_exc,
        )
