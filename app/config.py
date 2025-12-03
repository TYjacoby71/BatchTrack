from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Mapping
from urllib.parse import urlparse

_DEFAULT_ENV = "development"
_CANONICAL_ENV_VAR = "APP_ENV"
_LEGACY_ENV_VARS = ("BATCHTRACK_ENV", "FLASK_ENV", "ENVIRONMENT")
_VALID_ENVS = {"development", "testing", "staging", "production"}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class EnvironmentInfo:
    name: str
    source: str
    aliases: dict[str, str]


class EnvReader:
    def __init__(self, data: Mapping[str, str] | None = None):
        self._data = dict(data or os.environ)
        self.warnings: list[str] = []

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def _value(self, key: str) -> str | None:
        value = self._data.get(key)
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    def str(self, key: str, default: str | None = None) -> str | None:
        value = self._value(key)
        return value if value is not None else default

    def int(self, key: str, default: int = 0) -> int:
        value = self._value(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            self.warn(f"{key} expected integer but received {value!r}; falling back to {default}.")
            return default

    def float(self, key: str, default: float = 0.0) -> float:
        value = self._value(key)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            self.warn(f"{key} expected float but received {value!r}; falling back to {default}.")
            return default

    def bool(self, key: str, default: bool = False) -> bool:
        value = self._value(key)
        if value is None:
            return default
        lowered = value.lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
        self.warn(f"{key} expected boolean but received {value!r}; falling back to {default}.")
        return default

    def raw(self, key: str) -> str | None:
        return self._data.get(key)


def _normalized_env(value: str | None, *, default: str = _DEFAULT_ENV) -> str:
    if not value:
        return default
    return value.strip().lower() or default


def _normalize_db_url(url: str | None) -> str | None:
    if not url:
        return None
    return 'postgresql://' + url[len('postgres://'):] if url.startswith('postgres://') else url


def _extract_host(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc or parsed.path
    return host or None


def _derive_scheme(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    return parsed.scheme or None


def _resolve_ratelimit_uri(reader: EnvReader) -> str:
    candidate = reader.str('RATELIMIT_STORAGE_URI') or reader.str('RATELIMIT_STORAGE_URL')
    if candidate:
        return candidate
    redis_url = reader.str('REDIS_URL')
    if redis_url:
        return redis_url
    return 'memory://'


def _resolve_environment(reader: EnvReader) -> EnvironmentInfo:
    aliases: dict[str, str] = {}
    env_name: str | None = None
    source = 'default'

    for key in (_CANONICAL_ENV_VAR,) + _LEGACY_ENV_VARS:
        raw_value = reader._value(key)
        if raw_value is not None:
            aliases[key] = raw_value
            if env_name is None:
                normalized = _normalized_env(raw_value)
                env_name = normalized if normalized in _VALID_ENVS else None
                source = key
                if key != _CANONICAL_ENV_VAR:
                    reader.warn(f"{key} is deprecated; set {_CANONICAL_ENV_VAR} instead.")

    if env_name is None:
        reader.warn(f"No valid {_CANONICAL_ENV_VAR} provided; defaulting to {_DEFAULT_ENV}.")
        env_name = _DEFAULT_ENV
        source = 'default'

    return EnvironmentInfo(name=env_name, source=source, aliases=aliases)


env = EnvReader()
ENV_INFO = _resolve_environment(env)
ENVIRONMENT_VARIABLE_PRIORITY = (_CANONICAL_ENV_VAR,) + _LEGACY_ENV_VARS

_BASE_URL = (
    env.str('APP_BASE_URL')
    or env.str('EXTERNAL_BASE_URL')
    or env.str('PUBLIC_BASE_URL')
    or env.str('BATCHTRACK_BASE_URL')
)
_CANONICAL_HOST = env.str('APP_HOST') or env.str('CANONICAL_HOST') or _extract_host(_BASE_URL)
_PREFERRED_SCHEME = _derive_scheme(_BASE_URL)
_ALLOW_LOADTEST_LOGIN_BYPASS = env.bool('ALLOW_LOADTEST_LOGIN_BYPASS', False)
if not _ALLOW_LOADTEST_LOGIN_BYPASS and env.bool('LOADTEST_ALLOW_LOGIN_WITHOUT_CSRF', False):
    _ALLOW_LOADTEST_LOGIN_BYPASS = True
    env.warn('LOADTEST_ALLOW_LOGIN_WITHOUT_CSRF is deprecated; use ALLOW_LOADTEST_LOGIN_BYPASS.')


class BaseConfig:
    APP_ENV = ENV_INFO.name
    SECRET_KEY = env.str('FLASK_SECRET_KEY', 'devkey-please-change-in-production')

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True

    SESSION_LIFETIME_MINUTES = env.int('SESSION_LIFETIME_MINUTES', 60)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_LIFETIME_MINUTES)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    SESSION_USE_SIGNER = True
    SESSION_PERMANENT = True

    UPLOAD_FOLDER = 'static/product_images'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    EXTERNAL_BASE_URL = _BASE_URL
    CANONICAL_HOST = _CANONICAL_HOST
    PREFERRED_URL_SCHEME = _PREFERRED_SCHEME

    RATELIMIT_STORAGE_URI = _resolve_ratelimit_uri(env)
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI
    RATELIMIT_ENABLED = env.bool('RATELIMIT_ENABLED', True)
    RATELIMIT_DEFAULT = env.str('RATELIMIT_DEFAULT', '5000 per hour;1000 per minute')

    CACHE_TYPE = env.str('CACHE_TYPE', 'SimpleCache')
    CACHE_REDIS_URL = env.str('CACHE_REDIS_URL') or env.str('REDIS_URL')
    CACHE_DEFAULT_TIMEOUT = env.int('CACHE_DEFAULT_TIMEOUT', 120)

    BILLING_STATUS_CACHE_TTL = env.int('BILLING_STATUS_CACHE_TTL', 120)

    LOG_LEVEL = env.str('LOG_LEVEL', 'WARNING') or 'WARNING'
    ANON_REQUEST_LOG_LEVEL = env.str('ANON_REQUEST_LOG_LEVEL', 'DEBUG') or 'DEBUG'
    LOADTEST_LOG_LOGIN_FAILURE_CONTEXT = env.bool('LOADTEST_LOG_LOGIN_FAILURE_CONTEXT', False)
    ALLOW_LOADTEST_LOGIN_BYPASS = _ALLOW_LOADTEST_LOGIN_BYPASS

    EMAIL_PROVIDER = (env.str('EMAIL_PROVIDER', 'smtp') or 'smtp').lower()
    MAIL_SERVER = env.str('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = env.int('MAIL_PORT', 587)
    MAIL_USE_TLS = env.bool('MAIL_USE_TLS', True)
    MAIL_USE_SSL = env.bool('MAIL_USE_SSL', False)
    MAIL_USERNAME = env.str('MAIL_USERNAME')
    MAIL_PASSWORD = env.str('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = env.str('MAIL_DEFAULT_SENDER', 'noreply@batchtrack.app')

    SENDGRID_API_KEY = env.str('SENDGRID_API_KEY')
    POSTMARK_SERVER_TOKEN = env.str('POSTMARK_SERVER_TOKEN')
    MAILGUN_API_KEY = env.str('MAILGUN_API_KEY')
    MAILGUN_DOMAIN = env.str('MAILGUN_DOMAIN')

    STRIPE_PUBLISHABLE_KEY = env.str('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = env.str('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = env.str('STRIPE_WEBHOOK_SECRET')
    WHOP_API_KEY = env.str('WHOP_API_KEY')
    WHOP_APP_ID = env.str('WHOP_APP_ID')
    GOOGLE_OAUTH_CLIENT_ID = env.str('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = env.str('GOOGLE_OAUTH_CLIENT_SECRET')

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': env.int('SQLALCHEMY_POOL_SIZE', 80),
        'max_overflow': env.int('SQLALCHEMY_MAX_OVERFLOW', 40),
        'pool_pre_ping': True,
        'pool_recycle': env.int('SQLALCHEMY_POOL_RECYCLE', 1800),
        'pool_timeout': env.int('SQLALCHEMY_POOL_TIMEOUT', 30),
        'pool_use_lifo': True,
        'pool_reset_on_return': 'commit',
    }

    BILLING_CACHE_ENABLED = env.bool('BILLING_CACHE_ENABLED', True)
    BILLING_GATE_CACHE_TTL_SECONDS = env.int('BILLING_GATE_CACHE_TTL_SECONDS', 60)

    FEATURE_INVENTORY_ANALYTICS = env.bool('FEATURE_INVENTORY_ANALYTICS', True)
    FEATURE_BATCHBOT = env.bool('FEATURE_BATCHBOT', True)

    GOOGLE_AI_API_KEY = env.str('GOOGLE_AI_API_KEY') or env.str('GOOGLE_GENERATIVE_AI_API_KEY')
    GOOGLE_AI_DEFAULT_MODEL = env.str('GOOGLE_AI_DEFAULT_MODEL', 'gemini-1.5-flash') or 'gemini-1.5-flash'
    GOOGLE_AI_BATCHBOT_MODEL = env.str('GOOGLE_AI_BATCHBOT_MODEL') or GOOGLE_AI_DEFAULT_MODEL or 'gemini-1.5-pro'
    GOOGLE_AI_PUBLICBOT_MODEL = env.str('GOOGLE_AI_PUBLICBOT_MODEL', 'gemini-1.5-flash') or 'gemini-1.5-flash'
    GOOGLE_AI_ENABLE_SEARCH = env.bool('GOOGLE_AI_ENABLE_SEARCH', True)
    GOOGLE_AI_ENABLE_FILE_SEARCH = env.bool('GOOGLE_AI_ENABLE_FILE_SEARCH', True)
    GOOGLE_AI_SEARCH_TOOL = env.str('GOOGLE_AI_SEARCH_TOOL', 'google_search') or 'google_search'
    BATCHBOT_REQUEST_TIMEOUT_SECONDS = env.int('BATCHBOT_REQUEST_TIMEOUT_SECONDS', 45)
    BATCHBOT_DEFAULT_MAX_REQUESTS = env.int('BATCHBOT_DEFAULT_MAX_REQUESTS', 0)
    BATCHBOT_REQUEST_WINDOW_DAYS = env.int('BATCHBOT_REQUEST_WINDOW_DAYS', 30)
    BATCHBOT_CHAT_MAX_MESSAGES = env.int('BATCHBOT_CHAT_MAX_MESSAGES', 60)
    BATCHBOT_COST_PER_MILLION_INPUT = env.float('BATCHBOT_COST_PER_MILLION_INPUT', 0.35)
    BATCHBOT_COST_PER_MILLION_OUTPUT = env.float('BATCHBOT_COST_PER_MILLION_OUTPUT', 0.53)
    BATCHBOT_SIGNUP_BONUS_REQUESTS = env.int('BATCHBOT_SIGNUP_BONUS_REQUESTS', 20)
    BATCHBOT_REFILL_LOOKUP_KEY = env.str('BATCHBOT_REFILL_LOOKUP_KEY', 'batchbot_refill_100') or 'batchbot_refill_100'


class DevelopmentConfig(BaseConfig):
    ENV = 'development'
    DEBUG = True
    DEVELOPMENT = True
    SESSION_COOKIE_SECURE = False

    _db_url = _normalize_db_url(env.str('DATABASE_INTERNAL_URL')) or _normalize_db_url(env.str('DATABASE_URL'))
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
    RATELIMIT_STORAGE_URI = env.str('RATELIMIT_STORAGE_URI') or env.str('RATELIMIT_STORAGE_URL') or 'memory://'
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI


class TestingConfig(BaseConfig):
    ENV = 'testing'
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    RATELIMIT_STORAGE_URI = env.str('RATELIMIT_STORAGE_URI', 'memory://') or 'memory://'
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI
    SESSION_TYPE = 'filesystem'


class StagingConfig(BaseConfig):
    ENV = 'staging'
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(env.str('DATABASE_INTERNAL_URL')) or _normalize_db_url(env.str('DATABASE_URL'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_pre_ping': True,
        'pool_recycle': 1800,
    }
    _staging_ratelimit_uri = env.str('RATELIMIT_STORAGE_URI') or env.str('REDIS_URL') or 'memory://'
    RATELIMIT_STORAGE_URI = _staging_ratelimit_uri
    RATELIMIT_STORAGE_URL = _staging_ratelimit_uri


class ProductionConfig(BaseConfig):
    ENV = 'production'
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(env.str('DATABASE_INTERNAL_URL')) or _normalize_db_url(env.str('DATABASE_URL'))
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': env.int('SQLALCHEMY_POOL_SIZE', 80),
        'max_overflow': env.int('SQLALCHEMY_MAX_OVERFLOW', 40),
        'pool_pre_ping': True,
        'pool_recycle': 1800,
        'pool_timeout': env.int('SQLALCHEMY_POOL_TIMEOUT', 30),
        'pool_use_lifo': True,
    }
    _prod_ratelimit_uri = (
        env.str('RATELIMIT_STORAGE_URI')
        or env.str('REDIS_URL')
        or env.str('RATELIMIT_STORAGE_URL')
        or _resolve_ratelimit_uri(env)
    )
    RATELIMIT_STORAGE_URI = _prod_ratelimit_uri
    RATELIMIT_STORAGE_URL = _prod_ratelimit_uri
    LOG_LEVEL = env.str('LOG_LEVEL', 'INFO') or 'INFO'
    ALLOW_LOADTEST_LOGIN_BYPASS = False


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
}


def get_active_config_name() -> str:
    return ENV_INFO.name


def get_config():
    return config_map[get_active_config_name()]


Config = config_map[ENV_INFO.name]
ENV_DIAGNOSTICS = {
    'active': ENV_INFO.name,
    'source': ENV_INFO.source,
    'variables': ENV_INFO.aliases,
    'warnings': tuple(env.warnings),
    'priority': ENVIRONMENT_VARIABLE_PRIORITY,
}
