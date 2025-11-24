from __future__ import annotations

from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
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
limiter = Limiter(key_func=get_remote_address, default_limits=("200 per day", "50 per hour"))
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
