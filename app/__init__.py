import logging
import os
from typing import Any

from flask import Flask, redirect, render_template, url_for
from flask_login import current_user
from sqlalchemy.pool import StaticPool

from .authz import configure_login_manager
from .blueprints_registry import register_blueprints
from .extensions import cache, csrf, db, limiter, migrate, server_session
from .logging_config import configure_logging
from .middleware import register_middleware
from .template_context import register_template_context
from .utils.template_filters import register_template_filters

logger = logging.getLogger(__name__)


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    os.makedirs(app.instance_path, exist_ok=True)

    _load_base_config(app, config)
    _configure_sqlite_engine_options(app)
    _sync_env_overrides(app)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    _configure_cache(app)
    _configure_sessions(app)
    _configure_rate_limiter(app)

    configure_login_manager(app)
    register_middleware(app)
    register_blueprints(app)
    from . import models  # noqa: F401  # ensure models registered for Alembic

    register_template_context(app)
    register_template_filters(app)
    _add_core_routes(app)
    configure_logging(app)
    _install_global_resilience_handlers(app)

    from .management import register_commands

    register_commands(app)
    _run_optional_create_all(app)

    return app


def _load_base_config(app: Flask, config: dict[str, Any] | None) -> None:
    app.config.from_object("app.config.Config")
    if config:
        app.config.update(config)

    if app.config.get("TESTING"):
        app.config.setdefault("WTF_CSRF_ENABLED", False)

    if config and "DATABASE_URL" in config:
        app.config["SQLALCHEMY_DATABASE_URI"] = config["DATABASE_URL"]

    upload_dir = os.path.join(app.root_path, "static", "product_images")
    os.makedirs(upload_dir, exist_ok=True)
    app.config.setdefault("UPLOAD_FOLDER", upload_dir)


def _sync_env_overrides(app: Flask) -> None:
    redis_url_env = os.environ.get("REDIS_URL")
    if redis_url_env and not app.config.get("REDIS_URL"):
        app.config["REDIS_URL"] = redis_url_env


def _configure_cache(app: Flask) -> None:
    redis_url = app.config.get("REDIS_URL")
    cache_config = {
        "CACHE_TYPE": "RedisCache" if redis_url else "SimpleCache",
        "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT", 300),
    }
    if redis_url:
        cache_config["CACHE_REDIS_URL"] = redis_url

    cache.init_app(app, config=cache_config)
    if app.config.get("ENV") == "production" and cache_config["CACHE_TYPE"] != "RedisCache":
        raise RuntimeError("Redis cache not configured; SimpleCache is not permitted in production.")


def _configure_sessions(app: Flask) -> None:
    session_backend = None
    session_redis = None
    session_redis_url = app.config.get("REDIS_URL")

    if session_redis_url:
        try:
            import redis

            session_redis = redis.Redis.from_url(session_redis_url)
            session_backend = "redis"
        except Exception as exc:
            logger.warning("Failed to initialize Redis-backed session store (%s); falling back to filesystem.", exc)

    if session_backend == "redis" and session_redis is not None:
        app.config.setdefault("SESSION_TYPE", "redis")
        app.config.setdefault("SESSION_PERMANENT", True)
        app.config.setdefault("SESSION_USE_SIGNER", True)
        app.config["SESSION_REDIS"] = session_redis
    else:
        session_dir = os.path.join(app.instance_path, "session_files")
        os.makedirs(session_dir, exist_ok=True)
        app.config.setdefault("SESSION_FILE_DIR", session_dir)
        app.config.setdefault("SESSION_TYPE", "filesystem")
        app.config.setdefault("SESSION_PERMANENT", True)
        app.config.setdefault("SESSION_USE_SIGNER", True)
        if app.config.get("ENV") == "production":
            raise RuntimeError("Server-side sessions require Redis in production.")

    server_session.init_app(app)


def _configure_rate_limiter(app: Flask) -> None:
    storage_uri = (
        app.config.get("RATELIMIT_STORAGE_URI")
        or app.config.get("RATELIMIT_STORAGE_URL")
        or "memory://"
    )
    app.config["RATELIMIT_STORAGE_URI"] = storage_uri
    limiter.init_app(app)

    if app.config.get("ENV") == "production" and storage_uri.startswith("memory://"):
        raise RuntimeError("Rate limiter storage must be Redis-backed in production.")


def _run_optional_create_all(app: Flask) -> None:
    create_all_disabled = os.environ.get("SQLALCHEMY_DISABLE_CREATE_ALL")
    create_all_enabled = os.environ.get("SQLALCHEMY_ENABLE_CREATE_ALL") in {"1", "true", "True", "yes", "YES"}

    if create_all_disabled:
        logger.info("db.create_all() disabled via SQLALCHEMY_DISABLE_CREATE_ALL")
        return
    if not create_all_enabled:
        logger.info("db.create_all() not enabled; Alembic migrations are the source of truth")
        return

    logger.info("Local dev: creating tables via db.create_all()")
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created/verified")
        except Exception as exc:  # pragma: no cover - dev helper
            logger.warning("Database table creation skipped: %s", exc)

def _configure_sqlite_engine_options(app):
    """Configure SQLite engine options for testing/memory databases"""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if app.config.get("TESTING") or uri.startswith("sqlite"):
        opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
        # Remove pool args that SQLite memory + StaticPool don't accept
        opts.pop("pool_size", None)
        opts.pop("max_overflow", None)
        if uri == "sqlite:///:memory:":
            opts["poolclass"] = StaticPool
            opts["connect_args"] = {"check_same_thread": False}
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = opts

def _install_global_resilience_handlers(app):
    """Install global DB rollback and friendly maintenance handler."""
    from sqlalchemy.exc import OperationalError, DBAPIError, SQLAlchemyError
    from .extensions import db
    from flask import render_template

    @app.teardown_request
    def _rollback_on_error(exc):
        if exc is not None:
            try:
                db.session.rollback()
            except Exception:
                pass

    @app.errorhandler(OperationalError)
    @app.errorhandler(DBAPIError)
    def _db_error_handler(e):
        try:
            db.session.rollback()
        except Exception:
            pass
        # Return lightweight 503 page; avoid cascading errors if template missing
        try:
            return render_template("errors/maintenance.html"), 503
        except Exception:
            return ("Service temporarily unavailable. Please try again shortly.", 503)

def _add_core_routes(app):
    """Add core application routes"""
    @app.route("/")
    def index():
        """Main landing page with proper routing logic"""
        if current_user.is_authenticated:
            if current_user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))  # Developers go to developer dashboard
            else:
                return redirect(url_for('app_routes.dashboard'))  # Regular users go to user dashboard
        else:
            return render_template("homepage.html")  # Serve public homepage for unauthenticated users

    @app.route("/homepage")
    def homepage():
        """Public homepage - accessible to all users"""
        return render_template("homepage.html")

    @app.route("/public")
    def public_page():
        """Alternative public page"""
        return render_template("homepage.html")

def _setup_logging(app):
    """Retained for backward compatibility; logging is configured via logging_config."""
    pass