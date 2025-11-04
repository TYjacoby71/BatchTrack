import os
from datetime import timedelta


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
    'default': DevelopmentConfig,
}


def get_config():
    env = os.environ.get('FLASK_ENV') or os.environ.get('ENV') or 'development'
    
    # Check for production deployment on Replit or Render
    if (os.environ.get('REPLIT_DEPLOYMENT') == 'true' or 
        os.environ.get('RENDER') or  # Render sets this automatically
        env == 'production'):
        return ProductionConfig
    return config_map.get(env, DevelopmentConfig)


# Backwards compatibility for existing imports
Config = get_config()