import os
from datetime import timedelta

def _env_bool(key, default=False):
    return os.environ.get(key, str(default)).lower() == 'true'

def _get_sqlite_path():
    """Get SQLite path for local development"""
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)
    os.chmod(instance_path, 0o777)
    return f'sqlite:///{os.path.join(instance_path, "batchtrack.db")}'

class Config:
    # Core
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'devkey-please-change-in-production')
    DEBUG = _env_bool('FLASK_DEBUG')

    # Database - clean logic
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or _get_sqlite_path()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10, 'max_overflow': 20, 'pool_recycle': 3600, 'pool_pre_ping': True
    }

    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    is_production = _env_bool('REPLIT_DEPLOYMENT')
    SESSION_COOKIE_SECURE = is_production
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PREFERRED_URL_SCHEME = 'https' if is_production else 'http'

    # External Services
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = _env_bool('MAIL_USE_TLS', True)
    MAIL_USE_SSL = _env_bool('MAIL_USE_SSL')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@batchtrack.app')

    # API Keys
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    WHOP_API_KEY = os.environ.get('WHOP_API_KEY')
    WHOP_APP_ID = os.environ.get('WHOP_APP_ID')
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')