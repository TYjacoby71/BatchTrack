import logging
import os
from typing import Any

from flask import Flask, current_app, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.pool import StaticPool

from .authz import configure_login_manager
from .blueprints_registry import register_blueprints
from .config import ENV_DIAGNOSTICS
from .extensions import cache, csrf, db, limiter, migrate, server_session
from .logging_config import configure_logging
from .middleware import register_middleware
from .utils.cache_utils import should_bypass_cache
from .utils.redis_pool import get_redis_pool

logger = logging.getLogger(__name__)


def create_app(config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    os.makedirs(app.instance_path, exist_ok=True)

    _load_base_config(app, config)
    _apply_sqlalchemy_env_overrides(app)
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

    from .template_context import register_template_context
    from .utils.template_filters import register_template_filters

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
    app.config["ENV_DIAGNOSTICS"] = ENV_DIAGNOSTICS
    for warning in ENV_DIAGNOSTICS.get("warnings", ()):
        logger.warning("Environment configuration warning: %s", warning)

    if app.config.get("TESTING"):
        app.config.setdefault("WTF_CSRF_ENABLED", False)

    if config and "DATABASE_URL" in config:
        app.config["SQLALCHEMY_DATABASE_URI"] = config["DATABASE_URL"]

    upload_dir = os.path.join(app.root_path, "static", "product_images")
    os.makedirs(upload_dir, exist_ok=True)
    app.config.setdefault("UPLOAD_FOLDER", upload_dir)
    app.config.setdefault("BATCHTRACK_ORG_ID", 1)


def _apply_sqlalchemy_env_overrides(app: Flask) -> None:
    engine_opts = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}) or {})
    changed = False

    def _apply_int(env_key: str, option_key: str):
        nonlocal changed
        value = os.environ.get(env_key)
        if value in (None, ""):
            return
        try:
            engine_opts[option_key] = int(value)
            changed = True
        except ValueError:
            logger.warning("Invalid integer for %s: %s", env_key, value)

    def _apply_float(env_key: str, option_key: str):
        nonlocal changed
        value = os.environ.get(env_key)
        if value in (None, ""):
            return
        try:
            engine_opts[option_key] = float(value)
            changed = True
        except ValueError:
            logger.warning("Invalid float for %s: %s", env_key, value)

    _apply_int("SQLALCHEMY_POOL_SIZE", "pool_size")
    _apply_int("SQLALCHEMY_MAX_OVERFLOW", "max_overflow")
    _apply_float("SQLALCHEMY_POOL_TIMEOUT", "pool_timeout")

    if changed:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_opts


def _sync_env_overrides(app: Flask) -> None:
    redis_url_env = os.environ.get("REDIS_URL")
    if redis_url_env and not app.config.get("REDIS_URL"):
        app.config["REDIS_URL"] = redis_url_env


def _configure_cache(app: Flask) -> None:
    redis_url = app.config.get("REDIS_URL")
    cache_config = {
        "CACHE_DEFAULT_TIMEOUT": app.config.get("CACHE_DEFAULT_TIMEOUT", 300),
    }

    if redis_url:
        pool = get_redis_pool(app)
        if pool is not None:
            cache_config["CACHE_TYPE"] = "RedisCache"
            cache_config["CACHE_REDIS_URL"] = redis_url
            cache_config.setdefault("CACHE_OPTIONS", {})
            cache_config["CACHE_OPTIONS"]["connection_pool"] = pool
            logger.info("Redis cache configured with shared connection pool")
        else:
            cache_config["CACHE_TYPE"] = "SimpleCache"
            logger.warning("Unable to initialize Redis cache; falling back to SimpleCache.")
    else:
        cache_config["CACHE_TYPE"] = "SimpleCache"
        logger.info("Using SimpleCache (no Redis URL configured)")

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

            pool = get_redis_pool(app)
            if pool is not None:
                session_redis = redis.Redis(connection_pool=pool)
            else:
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
    if storage_uri.startswith("redis"):
        pool = get_redis_pool(app)
        if pool is not None:
            storage_options = dict(app.config.get("RATELIMIT_STORAGE_OPTIONS") or {})
            storage_options["connection_pool"] = pool
            app.config["RATELIMIT_STORAGE_OPTIONS"] = storage_options
    limiter.init_app(app)

    if app.config.get("ENV") == "production" and storage_uri.startswith("memory://"):
        raise RuntimeError("Rate limiter storage must be Redis-backed in production.")


def _run_optional_create_all(app: Flask) -> None:
    def _env_flag(key: str):
        value = os.environ.get(key)
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return None

    def _execute_create_all(reason: str):
        logger.info("Local dev: creating tables via db.create_all() (%s)", reason)
        with app.app_context():
            try:
                db.create_all()
                logger.info("Database tables created/verified")
            except Exception as exc:  # pragma: no cover - dev helper
                logger.warning("Database table creation skipped: %s", exc)

    create_all_flag = _env_flag("SQLALCHEMY_CREATE_ALL")
    if create_all_flag is None:
        logger.info("db.create_all() not enabled; Alembic migrations are the source of truth")
        return
    if create_all_flag is False:
        logger.info("db.create_all() disabled via SQLALCHEMY_CREATE_ALL=0")
        return
    _execute_create_all("SQLALCHEMY_CREATE_ALL")

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
    from flask import render_template, request
    from flask_wtf.csrf import CSRFError

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

    @app.errorhandler(CSRFError)
    def _csrf_error_handler(err: CSRFError):
        """Emit structured diagnostics so load tests can see *why* CSRF failed."""
        details = {
            "path": request.path,
            "endpoint": request.endpoint,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.user_agent.string if request.user_agent else None,
            "reason": err.description,
        }
        app.logger.warning("CSRF validation failed: %s", details)
        rendered = None
        try:
            rendered = render_template("errors/csrf.html", reason=err.description, details=details)
        except Exception:
            pass
        if rendered is not None:
            return rendered, 400
        return "CSRF validation failed. Please refresh and try again.", 400

def _add_core_routes(app):
    """Add core application routes"""
    def _render_public_homepage_response():
        """
        Serve the marketing homepage with Redis caching so anonymous traffic (and load tests)
        avoid re-rendering the full template on every hit.
        """
        cache_key = current_app.config.get("PUBLIC_HOMEPAGE_CACHE_KEY", "public:homepage:v1")
        try:
            from app.utils.settings import is_feature_enabled

            global_library_enabled = is_feature_enabled("FEATURE_GLOBAL_ITEM_LIBRARY")
            cache_key = f"{cache_key}:global_library:{'on' if global_library_enabled else 'off'}"
        except Exception:
            pass
        try:
            cache_ttl = int(current_app.config.get("PUBLIC_HOMEPAGE_CACHE_TTL", 600))
        except (TypeError, ValueError):
            cache_ttl = 600
        cache_ttl = max(0, cache_ttl)

        if cache_ttl and not should_bypass_cache():
            cached_page = cache.get(cache_key)
            if cached_page is not None:
                return cached_page

        rendered = render_template("homepage.html")
        if cache_ttl:
            try:
                cache.set(cache_key, rendered, timeout=cache_ttl)
            except Exception:
                # Homepage rendering should never fail because cache is unavailable.
                pass
        return rendered

    @app.route("/")
    def index():
        """Main landing page with proper routing logic"""
        if current_user.is_authenticated:
            if current_user.user_type == 'developer':
                return redirect(url_for('developer.dashboard'))  # Developers go to developer dashboard
            else:
                return redirect(url_for('app_routes.dashboard'))  # Regular users go to user dashboard
        else:
            return _render_public_homepage_response()  # Serve cached public homepage for unauthenticated users

    @app.route("/homepage")
    def homepage():
        """Public homepage - accessible to all users"""
        return _render_public_homepage_response()

    @app.route("/public")
    def public_page():
        """Alternative public page"""
        return _render_public_homepage_response()

def _setup_logging(app):
    """Retained for backward compatibility; logging is configured via logging_config."""
    pass

