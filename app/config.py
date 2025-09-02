import os
from datetime import timedelta

class Config:
    # Basic Flask Configuration
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')

    # Database Configuration
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Use PostgreSQL from environment
        SQLALCHEMY_DATABASE_URI = database_url
    else:
        # Fallback to SQLite for local development
        import os
        instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance')
        os.makedirs(instance_path, exist_ok=True)
        os.chmod(instance_path, 0o777)
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(instance_path, 'batchtrack.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
        'echo': False  # Set to True only for debugging
    }

    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_SECURE = os.environ.get('REPLIT_DEPLOYMENT') == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Security
    if os.environ.get('REPLIT_DEPLOYMENT') == 'true':
        PREFERRED_URL_SCHEME = 'https'

    # Flask-Mail Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@batchtrack.app')

    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Whop Configuration
    WHOP_API_KEY = os.environ.get('WHOP_API_KEY')
    WHOP_APP_ID = os.environ.get('WHOP_APP_ID')

    # OAuth Configuration
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')

    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')

    # Debug - disable in production
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true' and os.environ.get('FLASK_ENV') != 'production'