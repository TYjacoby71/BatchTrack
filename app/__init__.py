import os
import logging
from flask import Flask, redirect, url_for, render_template
from flask_login import current_user
from sqlalchemy.pool import StaticPool

# Import extensions and new modules
from .extensions import db, migrate, csrf, limiter, cache, server_session
from .authz import configure_login_manager
from .middleware import register_middleware
from .template_context import register_template_context
from .blueprints_registry import register_blueprints
from .utils.template_filters import register_template_filters
from .logging_config import configure_logging
from .blueprints.api.drawer_actions import drawer_actions_bp
from .blueprints.api.routes import api_bp

logger = logging.getLogger(__name__)

def create_app(config=None):
    """Create and configure Flask application"""
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    os.makedirs(app.instance_path, exist_ok=True)

    # Load configuration
    app.config.from_object("app.config.Config")
    if config:
        app.config.update(config)

    # Testing configuration
    if app.config.get('TESTING'):
        # Keep CSRF disabled for form tests, but allow login security to function
        app.config.setdefault("WTF_CSRF_ENABLED", False)

    # Tests pass DATABASE_URL; SQLAlchemy wants SQLALCHEMY_DATABASE_URI
    if config and "DATABASE_URL" in config:
        app.config["SQLALCHEMY_DATABASE_URI"] = config["DATABASE_URL"]

    app.config['UPLOAD_FOLDER'] = 'static/product_images'
    os.makedirs('static/product_images', exist_ok=True)

    # SQLite engine options for tests/memory databases
    _configure_sqlite_engine_options(app)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Configure cache (Redis in production, simple in development)
    cache_config = {
        'CACHE_TYPE': 'RedisCache' if app.config.get('REDIS_URL') else 'SimpleCache',
        'CACHE_DEFAULT_TIMEOUT': 300,
    }
    if app.config.get('REDIS_URL'):
        cache_config['CACHE_REDIS_URL'] = app.config['REDIS_URL']

    cache.init_app(app, config=cache_config)
    if app.config.get('ENV') == 'production' and cache_config.get('CACHE_TYPE') != 'RedisCache':
        message = "Redis cache not configured; falling back to SimpleCache is not permitted in production."
        logger.error(message)
        raise RuntimeError(message)

    # Configure server-side sessions
    session_backend = None
    session_redis = None
    redis_url = app.config.get('REDIS_URL')
    if redis_url:
        try:
            import redis  # type: ignore
            session_redis = redis.Redis.from_url(redis_url)
            session_backend = 'redis'
        except Exception as exc:
            logger.warning("Failed to initialize Redis-backed session store (%s); falling back to filesystem.", exc)
    if not session_backend:
        session_backend = 'filesystem'
        session_dir = os.path.join(app.instance_path, 'session_files')
        os.makedirs(session_dir, exist_ok=True)
        app.config.setdefault('SESSION_FILE_DIR', session_dir)

    if session_backend == 'redis' and session_redis is not None:
        app.config.setdefault('SESSION_TYPE', 'redis')
        app.config.setdefault('SESSION_PERMANENT', True)
        app.config.setdefault('SESSION_USE_SIGNER', True)
        app.config['SESSION_REDIS'] = session_redis
    else:
        app.config.setdefault('SESSION_TYPE', 'filesystem')
        app.config.setdefault('SESSION_PERMANENT', True)
        app.config.setdefault('SESSION_USE_SIGNER', True)
        if app.config.get('ENV') == 'production':
            message = "Server-side sessions require Redis in production. Set REDIS_URL to a Redis instance."
            logger.error(message)
            raise RuntimeError(message)

    server_session.init_app(app)

    # Configure rate limiter with Redis storage in production
    limiter_storage_uri = app.config.get('RATELIMIT_STORAGE_URI')
    if limiter_storage_uri:
        app.config['RATELIMIT_STORAGE_URI'] = limiter_storage_uri
    limiter.init_app(app)
    if app.config.get('ENV') == 'production' and (not limiter_storage_uri or str(limiter_storage_uri).startswith('memory://')):
        message = "Rate limiter storage must be Redis-backed in production. Set RATELIMIT_STORAGE_URI accordingly."
        logger.error(message)
        raise RuntimeError(message)

    configure_login_manager(app)

    # Session lifetime should come from config classes; avoid overriding here

    # Clear all dismissed alerts on app restart - Flask 2.2+ compatible
    with app.app_context():
        # Sessions will be cleared automatically on app restart since we're using the default session interface
        pass

    # Register application components
    register_middleware(app)
    register_blueprints(app)
    # Import models for Alembic
    from . import models

    # Only create tables when explicitly enabled for local/dev throwaway setups.
    # Honor legacy disable flag if present.
    create_all_disabled = os.environ.get('SQLALCHEMY_DISABLE_CREATE_ALL')
    create_all_enabled = os.environ.get('SQLALCHEMY_ENABLE_CREATE_ALL') in {"1", "true", "True", "yes", "YES"}

    if create_all_disabled:
        logger.info("🔒 db.create_all() disabled via SQLALCHEMY_DISABLE_CREATE_ALL")
    elif create_all_enabled:
        logger.info("🔧 Local dev: creating tables via db.create_all()")
        with app.app_context():
            try:
                db.create_all()
                logger.info("✅ Database tables created/verified")
            except Exception as e:
                logger.warning(f"⚠️  Database table creation skipped: {e}")
    else:
        logger.info("🔒 db.create_all() not enabled; Alembic migrations are the source of truth")

    # Register context processors
    register_template_context(app)
    # Register template filters
    register_template_filters(app)


    # Add core routes
    _add_core_routes(app)

    # Configure centralized logging
    configure_logging(app)

    # Install global resilience (DB rollback + maintenance page)
    _install_global_resilience_handlers(app)

    # Register CLI commands
    from .management import register_commands
    register_commands(app)

    return app

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


def _configure_cache(app):
    """Initialise the shared cache (Redis in production, NullCache otherwise)."""
    env = os.environ.get('ENV', 'development').lower()
    cache_type = app.config.get('CACHE_TYPE')
    redis_url = app.config.get('CACHE_REDIS_URL') or app.config.get('REDIS_URL')
    cache_timeout = app.config.get('CACHE_DEFAULT_TIMEOUT', 300)

    if not cache_type:
        if redis_url:
            cache_type = 'RedisCache'
        else:
            cache_type = 'NullCache'

    if cache_type == 'RedisCache' and not redis_url:
        raise RuntimeError('CACHE_REDIS_URL (or REDIS_URL) must be set when using RedisCache.')

    if cache_type == 'NullCache' and env == 'production':
        raise RuntimeError('A shared cache backend (e.g. Redis) is required in production.')

    cache_config = {
        'CACHE_TYPE': cache_type,
        'CACHE_DEFAULT_TIMEOUT': cache_timeout,
    }

    if cache_type == 'RedisCache':
        cache_config['CACHE_REDIS_URL'] = redis_url

    cache.init_app(app, config=cache_config)


def _configure_rate_limiter(app):
    """Initialise limiter with shared storage (Redis) when available."""
    env = os.environ.get('ENV', 'development').lower()
    storage_uri = (
        app.config.get('RATELIMIT_STORAGE_URI')
        or app.config.get('RATELIMIT_STORAGE_URL')
        or 'memory://'
    )

    if storage_uri.startswith('memory://') and env == 'production':
        raise RuntimeError('A shared rate limit storage backend is required in production.')

    limiter.init_app(app, storage_uri=storage_uri)

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