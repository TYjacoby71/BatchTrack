import os
from datetime import timedelta


_ENV_ALIASES = {
    'prod': 'production',
    'production': 'production',
    'live': 'production',
    'staging': 'staging',
    'stage': 'staging',
    'test': 'testing',
    'testing': 'testing',
    'qa': 'testing',
    'dev': 'development',
    'development': 'development',
    'default': 'development',
}


def _determine_environment(default: str = 'development') -> str:
    """Resolve the active environment name from multiple environment variables."""

    def _normalize(value: str | None) -> str | None:
        if not value:
            return None
        normalized = value.strip().lower()
        return _ENV_ALIASES.get(normalized, normalized)

    # Honor explicit ENV first, then FLASK_ENV
    env_candidates = (
        os.environ.get('ENV'),
        os.environ.get('FLASK_ENV'),
    )

    for candidate in env_candidates:
        normalized = _normalize(candidate)
        if normalized in _ENV_ALIASES.values():
            return normalized

    # If FLASK_DEBUG is explicitly enabled, favor development defaults
    flask_debug = os.environ.get('FLASK_DEBUG')
    if flask_debug and flask_debug.strip().lower() in {'1', 'true', 'yes', 'on'}:
        return 'development'

    return _ENV_ALIASES.get(default, 'development')


def _normalize_db_url(url: str | None) -> str | None:
    if not url:
        return None
    return 'postgresql://' + url[len('postgres://'):] if url.startswith('postgres://') else url


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

    # Uploads
    UPLOAD_FOLDER = 'static/product_images'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')

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
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    WHOP_API_KEY = os.environ.get('WHOP_API_KEY')
    WHOP_APP_ID = os.environ.get('WHOP_APP_ID')
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')


class DevelopmentConfig(BaseConfig):
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

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 3600,
        'echo': False,
    }


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    # In tests we often use file-based temp SQLite from fixtures; default to memory
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    # Add rate limiter storage configuration for tests
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')


class StagingConfig(BaseConfig):
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
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'memory://'


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.environ.get('DATABASE_INTERNAL_URL')) or _normalize_db_url(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 20,
        'max_overflow': 30,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_timeout': 30,
    }
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or os.environ.get('RATELIMIT_STORAGE_URL')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
}


def get_active_config_name(default: str = 'development') -> str:
    """Return the canonical configuration key for the current environment."""
    env_name = _determine_environment(default)
    return env_name if env_name in config_map else default


def get_config(default: str = 'development'):
    """Return the config class for the active environment."""
    config_name = get_active_config_name(default)
    return config_map[config_name]


# Backwards compatibility for existing imports
Config = get_config()