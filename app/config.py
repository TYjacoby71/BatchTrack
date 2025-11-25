import os
from datetime import timedelta


_DEFAULT_ENV = 'development'


def _normalized_env(value: str | None, *, default: str = _DEFAULT_ENV) -> str:
    if not value:
        return default
    return value.strip().lower() or default


def _normalize_db_url(url: str | None) -> str | None:
    if not url:
        return None
    return 'postgresql://' + url[len('postgres://'):] if url.startswith('postgres://') else url


def _resolve_ratelimit_uri() -> str:
    """Resolve the rate limit storage URI with backwards compatibility."""
    candidate = os.environ.get('RATELIMIT_STORAGE_URI') or os.environ.get('RATELIMIT_STORAGE_URL')
    if candidate:
        return candidate
    redis_url = os.environ.get('REDIS_URL')
    if redis_url:
        return redis_url
    return 'memory://'


def _env_int(key, default):
    """Helper to parse environment integers with fallback."""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


class BaseConfig:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')

    # Database defaults; subclasses should set SQLALCHEMY_DATABASE_URI explicitly
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True

    # Sessions & security
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    SESSION_USE_SIGNER = True
    SESSION_PERMANENT = True

    # Uploads
    UPLOAD_FOLDER = 'static/product_images'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

   # Rate limiting & Cache
    RATELIMIT_STORAGE_URI = _resolve_ratelimit_uri()
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI  # Backwards compatibility

    # Cache / shared state
    CACHE_TYPE = os.environ.get('CACHE_TYPE', 'SimpleCache') # Default to SimpleCache if Redis isn't set
    CACHE_REDIS_URL = os.environ.get('CACHE_REDIS_URL') or os.environ.get('REDIS_URL')
    CACHE_DEFAULT_TIMEOUT = _env_int('CACHE_DEFAULT_TIMEOUT', 120)

    # Billing cache tuning
    BILLING_STATUS_CACHE_TTL = _env_int('BILLING_STATUS_CACHE_TTL', 120)

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')
    ANON_REQUEST_LOG_LEVEL = os.environ.get('ANON_REQUEST_LOG_LEVEL', 'DEBUG')

    # Email - Support multiple providers
    EMAIL_PROVIDER = os.environ.get('EMAIL_PROVIDER', 'smtp').lower()

    # SMTP (default)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@batchtrack.app')

    # Alternative providers
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')
    POSTMARK_SERVER_TOKEN = os.environ.get('POSTMARK_SERVER_TOKEN')
    MAILGUN_API_KEY = os.environ.get('MAILGUN_API_KEY')
    MAILGUN_DOMAIN = os.environ.get('MAILGUN_DOMAIN')

    # Billing / OAuth
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    WHOP_API_KEY = os.environ.get('WHOP_API_KEY')
    WHOP_APP_ID = os.environ.get('WHOP_APP_ID')
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

    # Enhanced SQLAlchemy pool configuration for high concurrency
    # These are default values; specific environments may override them.
    # For 10k users, ProductionConfig should be the primary beneficiary.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': _env_int('SQLALCHEMY_POOL_SIZE', 20), # Default for base
        'max_overflow': _env_int('SQLALCHEMY_MAX_OVERFLOW', 30), # Default for base
        'pool_pre_ping': True,
        'pool_recycle': _env_int('SQLALCHEMY_POOL_RECYCLE', 1800),
        'pool_timeout': _env_int('SQLALCHEMY_POOL_TIMEOUT', 30),
        'pool_use_lifo': True,
    }

    # Billing cache configuration
    BILLING_CACHE_ENABLED = os.environ.get('BILLING_CACHE_ENABLED', 'true').lower() == 'true'
    BILLING_GATE_CACHE_TTL_SECONDS = _env_int('BILLING_GATE_CACHE_TTL_SECONDS', 60)

    # Feature flags
    FEATURE_INVENTORY_ANALYTICS = os.environ.get('FEATURE_INVENTORY_ANALYTICS', 'true').lower() == 'true'

    # Google AI / BatchBot integration
    GOOGLE_AI_API_KEY = os.environ.get('GOOGLE_AI_API_KEY') or os.environ.get('GOOGLE_GENERATIVE_AI_API_KEY')
    GOOGLE_AI_DEFAULT_MODEL = os.environ.get('GOOGLE_AI_DEFAULT_MODEL', 'gemini-1.5-flash')
    GOOGLE_AI_BATCHBOT_MODEL = os.environ.get('GOOGLE_AI_BATCHBOT_MODEL', GOOGLE_AI_DEFAULT_MODEL or 'gemini-1.5-pro')
    GOOGLE_AI_PUBLICBOT_MODEL = os.environ.get('GOOGLE_AI_PUBLICBOT_MODEL', 'gemini-1.5-flash')
    GOOGLE_AI_ENABLE_SEARCH = os.environ.get('GOOGLE_AI_ENABLE_SEARCH', 'true').lower() == 'true'
    GOOGLE_AI_ENABLE_FILE_SEARCH = os.environ.get('GOOGLE_AI_ENABLE_FILE_SEARCH', 'true').lower() == 'true'
    GOOGLE_AI_SEARCH_TOOL = os.environ.get('GOOGLE_AI_SEARCH_TOOL', 'google_search')
    BATCHBOT_REQUEST_TIMEOUT_SECONDS = _env_int('BATCHBOT_REQUEST_TIMEOUT_SECONDS', 45)
    BATCHBOT_DEFAULT_MAX_REQUESTS = _env_int('BATCHBOT_DEFAULT_MAX_REQUESTS', 0)
    BATCHBOT_REQUEST_WINDOW_DAYS = _env_int('BATCHBOT_REQUEST_WINDOW_DAYS', 30)
    BATCHBOT_COST_PER_MILLION_INPUT = float(os.environ.get('BATCHBOT_COST_PER_MILLION_INPUT', 0.35))
    BATCHBOT_COST_PER_MILLION_OUTPUT = float(os.environ.get('BATCHBOT_COST_PER_MILLION_OUTPUT', 0.53))
    BATCHBOT_SIGNUP_BONUS_REQUESTS = _env_int('BATCHBOT_SIGNUP_BONUS_REQUESTS', 20)


class DevelopmentConfig(BaseConfig):
    ENV = 'development'
    DEBUG = True
    DEVELOPMENT = True
    SESSION_COOKIE_SECURE = False

    # Prefer internal URL (Render) then DATABASE_URL; else SQLite for local dev
    _db_url = _normalize_db_url(os.environ.get('DATABASE_INTERNAL_URL')) or _normalize_db_url(os.environ.get('DATABASE_URL'))
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance')
        os.makedirs(instance_path, exist_ok=True)
        os.chmod(instance_path, 0o777)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(instance_path, 'batchtrack.db')

    # Development specific engine options, less aggressive than production
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'echo': False,
    }
    RATELIMIT_STORAGE_URI = (
        os.environ.get('RATELIMIT_STORAGE_URI')
        or os.environ.get('RATELIMIT_STORAGE_URL')
        or 'memory://'
    )
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI


class TestingConfig(BaseConfig):
    ENV = 'testing'
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    # In tests we often use file-based temp SQLite from fixtures; default to memory
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    # Add rate limiter storage configuration for tests
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI
    SESSION_TYPE = 'filesystem'


class StagingConfig(BaseConfig):
    ENV = 'staging'
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.environ.get('DATABASE_INTERNAL_URL')) or _normalize_db_url(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }
    _staging_ratelimit_uri = os.environ.get('RATELIMIT_STORAGE_URI') or os.environ.get('REDIS_URL') or 'memory://'
    RATELIMIT_STORAGE_URI = _staging_ratelimit_uri
    RATELIMIT_STORAGE_URL = _staging_ratelimit_uri


class ProductionConfig(BaseConfig):
    ENV = 'production'
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.environ.get('DATABASE_INTERNAL_URL')) or _normalize_db_url(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.environ.get('SQLALCHEMY_POOL_SIZE', 80)),
        'max_overflow': int(os.environ.get('SQLALCHEMY_MAX_OVERFLOW', 40)),
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_timeout': int(os.environ.get('SQLALCHEMY_POOL_TIMEOUT', 30)),
    }
    _prod_ratelimit_uri = os.environ.get('RATELIMIT_STORAGE_URI') or os.environ.get('REDIS_URL') or os.environ.get('RATELIMIT_STORAGE_URL') or _resolve_ratelimit_uri()
    RATELIMIT_STORAGE_URI = _prod_ratelimit_uri
    RATELIMIT_STORAGE_URL = _prod_ratelimit_uri
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
}


def get_active_config_name() -> str:
    """Return the canonical configuration key for the current environment."""
    env_name = _normalized_env(os.environ.get('FLASK_ENV'), default=_DEFAULT_ENV)
    return env_name if env_name in config_map else _DEFAULT_ENV


def get_config():
    """Return the config class for the active environment."""
    config_name = get_active_config_name()
    return config_map[config_name]


# Backwards compatibility for existing imports
Config = get_config()