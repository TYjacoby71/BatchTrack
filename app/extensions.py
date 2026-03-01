"""Flask extensions and shared instances.

Synopsis:
Initialize shared extensions (DB, cache, limiter, sessions) for the app.

Glossary:
- Extension: Flask add-on providing shared infrastructure (DB, cache, auth).
- Limiter key: Identifier used to rate-limit requests.
"""

from __future__ import annotations
import logging

from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

logger = logging.getLogger(__name__)


__all__ = [
    "db",
    "migrate",
    "csrf",
    "cache",
    "limiter",
    "server_session",
    "mail",
    "login_manager",
]

db = SQLAlchemy()
migrate = Migrate(compare_type=True, render_as_batch=True)
csrf = CSRFProtect()
cache = Cache()


# --- Limiter key ---
# Purpose: Determine rate limiting key for a request.
def _limiter_key_func():
    """Use per-user keys for authenticated traffic; fall back to IP address."""
    try:
        if current_user.is_authenticated:
            user_id = current_user.get_id()
            if user_id:
                return f"user:{user_id}"
    except Exception:
        logger.warning("Suppressed exception fallback at app/extensions.py:48", exc_info=True)
        pass
    return get_remote_address()


limiter = Limiter(key_func=_limiter_key_func)
server_session = Session()

try:
    from flask_mail import Mail

    mail = Mail()
except ImportError:  # pragma: no cover - optional dependency

    class _MailStub:
        def send(self, *_, **__):
            raise RuntimeError("Flask-Mail is not installed; install it to send email.")

    mail = _MailStub()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "info"


# --- Login manager loader ---
# Purpose: Load user for Flask-Login sessions.
@login_manager.user_loader
def load_user(user_id: str):
    from sqlalchemy.orm import joinedload

    from .models import User

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return None
    user = db.session.get(User, user_id_int, options=[joinedload(User.organization)])
    return user
