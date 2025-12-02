from __future__ import annotations

from flask import current_app
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

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


def _default_rate_limits():
    """Resolve default rate limits from config or fall back to safe defaults."""
    config_value = current_app.config.get("RATELIMIT_DEFAULT")
    if isinstance(config_value, str) and config_value.strip():
        normalized = (
            config_value.replace(",", ";")
            .replace("|", ";")
            .split(";")
        )
        limits = [entry.strip() for entry in normalized if entry.strip()]
        if limits:
            return limits
    return ["5000 per hour", "1000 per minute"]


def _limiter_key_func():
    """Use per-user keys for authenticated traffic; fall back to IP address."""
    try:
        if current_user.is_authenticated:
            user_id = current_user.get_id()
            if user_id:
                return f"user:{user_id}"
    except Exception:
        pass
    return get_remote_address()


limiter = Limiter(
    key_func=_limiter_key_func,
    default_limits=_default_rate_limits,
)
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


@login_manager.user_loader
def load_user(user_id: str):
    from .models import User

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        return None
    return db.session.get(User, user_id_int)