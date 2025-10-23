import os
from datetime import timedelta


def _normalize_db_url(url: str | None) -> str | None:
    """Normalize Postgres URLs to the postgresql:// scheme."""
    if not url:
        return None
    return 'postgresql://' + url[len('postgres://'):] if url.startswith('postgres://') else url


def _default_sqlite_uri() -> str:
    """Make project-local SQLite DB under instance/ for development when no DATABASE_URL is provided."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    instance_path = os.path.join(base_dir, 'instance')
    os.makedirs(instance_path, exist_ok=True)
    try:
        os.chmod(instance_path, 0o755)
    except Exception:
        pass
    return 'sqlite:///' + os.path.join(instance_path, 'batchtrack.db')


def _resolve_database_url() -> str:
    """Prefer internal DB URL (Render), then DATABASE_URL, else default SQLite."""
    url = (
        _normalize_db_url(os.environ.get('DATABASE_INTERNAL_URL'))
        or _normalize_db_url(os.environ.get('DATABASE_URL'))
    )
    return url or _default_sqlite_uri()


class BaseConfig:
    """Base configuration shared across environments."""
    # Flask basics
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')
    DEBUG = False
    TESTING = False

    # Database
    SQLALCHEMY_DATABASE_URI = _resolve_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Conservative defaults; tuned in env-specific classes
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }

    # Manage schema via Alembic by default; allow opt-in create_all in dev
    SQLALCHEMY_ENABLE_CREATE_ALL = os.environ.get('SQLALCHEMY_ENABLE_CREATE_ALL') == '1'

    # Sessions / cookies
    PERMANENT_SESSION_LIFETIME = timedelta(days=31)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('REPLIT_DEPLOYMENT') == 'true'
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        PREFERRED_URL_SCHEME = 'https'

    # Uploads
    UPLOAD_FOLDER = 'static/product_images'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # Security / CSRF
    WTF_CSRF_ENABLED = True

    # Rate limiting (memory default; override with REDIS_URL in prod)
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')

    # Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@batchtrack.app')

    # Billing / Integrations
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    WHOP_API_KEY = os.environ.get('WHOP_API_KEY')
    WHOP_APP_ID = os.environ.get('WHOP_APP_ID')

    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # Prefer local env DATABASE_URL; else project sqlite
    SQLALCHEMY_DATABASE_URI = _resolve_database_url()
    # Relaxed cookies
    SESSION_COOKIE_SECURE = False
    # Developer-friendly engine tuning
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 600,
    }


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    # Use in-memory SQLite; app factory adjusts engine options for :memory:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    # Disable rate limiting by default in tests
    RATELIMIT_ENABLED = False


class StagingConfig(BaseConfig):
    # Production-like
    SQLALCHEMY_DATABASE_URI = _resolve_database_url()
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')


class ProductionConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = _resolve_database_url()
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PREFERRED_URL_SCHEME = 'https'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 30,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_timeout': 30,
    }
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or os.environ.get('RATELIMIT_STORAGE_URL')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


# Configuration selector
config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}


def get_config():
    """Return a config class based on environment variables."""
    # Special case for Replit deployment
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        return ProductionConfig
    env = os.environ.get('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)


# Backward compatibility: app factory imports `app.config.Config`
Config = get_config()

# Friendly log for visibility; avoid misleading engine type
try:
    db_uri_preview = (Config.SQLALCHEMY_DATABASE_URI or '')[:60]
    print(f"🔧 CONFIG: Using database: {db_uri_preview}...")
except Exception:
    pass