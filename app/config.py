"""Application configuration resolution and defaults.

Synopsis:
Loads environment values via the config schema and exposes Flask config classes.

Glossary:
- Env schema: Canonical list of env keys and defaults.
- Config class: Environment-specific configuration class for Flask.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Mapping
from urllib.parse import urlparse

from .config_schema import resolve_settings

_DEFAULT_ENV = "development"
_ENV_KEY = "FLASK_ENV"
_VALID_ENVS = {"development", "testing", "staging", "production"}
_FORBIDDEN_ENV_KEYS = ("APP_ENV", "BATCHTRACK_ENV", "ENVIRONMENT")
_FORBIDDEN_FLAGS = ("ALLOW_LOADTEST_LOGIN_BYPASS", "LOADTEST_ALLOW_LOGIN_WITHOUT_CSRF")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


# --- EnvironmentInfo ---
# Purpose: Hold the resolved runtime environment metadata.
@dataclass(frozen=True)
class EnvironmentInfo:
    name: str
    source: str
    raw_value: str


# --- EnvReader ---
# Purpose: Read and coerce environment values with warnings.
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


# --- Normalize environment ---
# Purpose: Coerce the environment name into a supported value.
def _normalized_env(value: str | None, *, default: str = _DEFAULT_ENV) -> str:
    if not value:
        return default
    return value.strip().lower() or default


# --- Normalize DB URL ---
# Purpose: Normalize postgres:// URLs into sqlalchemy-friendly formats.
def _normalize_db_url(url: str | None) -> str | None:
    if not url:
        return None
    return 'postgresql://' + url[len('postgres://'):] if url.startswith('postgres://') else url


# --- Extract host ---
# Purpose: Pull the hostname from a URL or host string.
def _extract_host(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value if "://" in value else f"https://{value}")
    host = parsed.netloc or parsed.path
    return host or None


# --- Derive scheme ---
# Purpose: Infer the scheme (http/https) from a base URL.
def _derive_scheme(base_url: str | None) -> str | None:
    if not base_url:
        return None
    parsed = urlparse(base_url)
    return parsed.scheme or None


# --- Resolve rate limit URI ---
# Purpose: Choose the rate limiter storage URI from settings.
def _resolve_ratelimit_uri(settings: Mapping[str, Any]) -> str:
    candidate = settings.get("RATELIMIT_STORAGE_URI")
    if candidate:
        return candidate
    redis_url = settings.get("REDIS_URL")
    if redis_url:
        return redis_url
    return "memory://"


# --- Resolve environment ---
# Purpose: Validate the configured environment and return metadata.
def _resolve_environment(reader: EnvReader) -> EnvironmentInfo:
    for key in _FORBIDDEN_ENV_KEYS:
        if reader.raw(key) not in (None, ""):
            raise RuntimeError(
                f"{key} is no longer supported. Set {_ENV_KEY} to one of {sorted(_VALID_ENVS)} instead."
            )

    raw_value = reader.str(_ENV_KEY, _DEFAULT_ENV) or _DEFAULT_ENV
    normalized = _normalized_env(raw_value)
    if normalized not in _VALID_ENVS:
        raise RuntimeError(
            f"Invalid {_ENV_KEY}={raw_value!r}. Expected one of {sorted(_VALID_ENVS)}."
        )
    return EnvironmentInfo(name=normalized, source=_ENV_KEY, raw_value=raw_value)


# --- Resolve base URL ---
# Purpose: Determine APP_BASE_URL for the active environment.
def _resolve_base_url(reader: EnvReader, env_name: str) -> str:
    value = reader.str('APP_BASE_URL')
    if value:
        return value
    if env_name in {'development', 'testing'}:
        fallback = 'http://localhost:5000'
        reader.warn(
            "APP_BASE_URL not set; defaulting to http://localhost:5000 for local/testing environments."
        )
        return fallback
    raise RuntimeError('APP_BASE_URL must be set for staging and production environments.')


# --- Preferred scheme ---
# Purpose: Pick the canonical scheme for redirects and links.
def _preferred_scheme(base_url: str, env_name: str) -> str:
    scheme = _derive_scheme(base_url)
    if scheme:
        return scheme
    return 'http' if env_name == 'development' else 'https'


env = EnvReader()
ENV_INFO = _resolve_environment(env)
SETTINGS, SETTINGS_META, SCHEMA_WARNINGS = resolve_settings(env._data, ENV_INFO.name)
env.warnings.extend(SCHEMA_WARNINGS)

for flag in _FORBIDDEN_FLAGS:
    if env.raw(flag) not in (None, ""):
        raise RuntimeError(
            f"{flag} has been removed. Load tests must behave like real clients and supply CSRF tokens."
        )

_BASE_URL = SETTINGS.get("APP_BASE_URL")
if not _BASE_URL:
    _BASE_URL = _resolve_base_url(env, ENV_INFO.name)
_CANONICAL_HOST = SETTINGS.get("APP_HOST") or _extract_host(_BASE_URL)
_PREFERRED_SCHEME = _preferred_scheme(_BASE_URL, ENV_INFO.name)


# --- BaseConfig ---
# Purpose: Define shared configuration defaults for all environments.
class BaseConfig:
    FLASK_ENV = ENV_INFO.name
    SECRET_KEY = SETTINGS.get("FLASK_SECRET_KEY")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_RECORD_QUERIES = True

    SESSION_LIFETIME_MINUTES = SETTINGS.get("SESSION_LIFETIME_MINUTES", 60)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=SESSION_LIFETIME_MINUTES)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    WTF_CSRF_ENABLED = True
    SESSION_USE_SIGNER = True
    SESSION_PERMANENT = True

    UPLOAD_FOLDER = 'static/product_images'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    APP_BASE_URL = _BASE_URL
    EXTERNAL_BASE_URL = _BASE_URL
    CANONICAL_HOST = _CANONICAL_HOST
    PREFERRED_URL_SCHEME = _PREFERRED_SCHEME

    RATELIMIT_STORAGE_URI = _resolve_ratelimit_uri(SETTINGS)
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI
    RATELIMIT_ENABLED = SETTINGS.get("RATELIMIT_ENABLED", True)
    RATELIMIT_DEFAULT = SETTINGS.get("RATELIMIT_DEFAULT", "5000 per hour;1000 per minute")
    RATELIMIT_SWALLOW_ERRORS = SETTINGS.get("RATELIMIT_SWALLOW_ERRORS", True)

    REDIS_URL = SETTINGS.get("REDIS_URL")
    CACHE_TYPE = SETTINGS.get("CACHE_TYPE", "SimpleCache")
    CACHE_REDIS_URL = SETTINGS.get("REDIS_URL")
    CACHE_DEFAULT_TIMEOUT = SETTINGS.get("CACHE_DEFAULT_TIMEOUT", 120)
    INGREDIENT_LIST_CACHE_TTL = SETTINGS.get("INGREDIENT_LIST_CACHE_TTL", 120)
    RECIPE_LIST_CACHE_TTL = SETTINGS.get("RECIPE_LIST_CACHE_TTL", 180)
    RECIPE_LIST_PAGE_SIZE = SETTINGS.get("RECIPE_LIST_PAGE_SIZE", 10)
    PRODUCT_LIST_CACHE_TTL = SETTINGS.get("PRODUCT_LIST_CACHE_TTL", 180)
    GLOBAL_LIBRARY_CACHE_TTL = SETTINGS.get("GLOBAL_LIBRARY_CACHE_TTL", 300)
    RECIPE_LIBRARY_CACHE_TTL = SETTINGS.get("RECIPE_LIBRARY_CACHE_TTL", 180)
    RECIPE_FORM_CACHE_TTL = SETTINGS.get("RECIPE_FORM_CACHE_TTL", 60)

    BILLING_STATUS_CACHE_TTL = SETTINGS.get("BILLING_STATUS_CACHE_TTL", 120)

    LOG_LEVEL = SETTINGS.get("LOG_LEVEL") or "WARNING"
    ANON_REQUEST_LOG_LEVEL = SETTINGS.get("ANON_REQUEST_LOG_LEVEL") or "DEBUG"
    LOG_REDACT_PII = SETTINGS.get("LOG_REDACT_PII", True)
    DISABLE_SECURITY_HEADERS = SETTINGS.get("DISABLE_SECURITY_HEADERS", False)

    EMAIL_PROVIDER = (SETTINGS.get("EMAIL_PROVIDER", "smtp") or "smtp").lower()
    MAIL_SERVER = SETTINGS.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = SETTINGS.get("MAIL_PORT", 587)
    MAIL_USE_TLS = SETTINGS.get("MAIL_USE_TLS", True)
    MAIL_USE_SSL = SETTINGS.get("MAIL_USE_SSL", False)
    MAIL_USERNAME = SETTINGS.get("MAIL_USERNAME")
    MAIL_PASSWORD = SETTINGS.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = SETTINGS.get("MAIL_DEFAULT_SENDER", "noreply@batchtrack.app")

    SENDGRID_API_KEY = SETTINGS.get("SENDGRID_API_KEY")
    POSTMARK_SERVER_TOKEN = SETTINGS.get("POSTMARK_SERVER_TOKEN")
    MAILGUN_API_KEY = SETTINGS.get("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = SETTINGS.get("MAILGUN_DOMAIN")

    STRIPE_PUBLISHABLE_KEY = SETTINGS.get("STRIPE_PUBLISHABLE_KEY")
    STRIPE_SECRET_KEY = SETTINGS.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = SETTINGS.get("STRIPE_WEBHOOK_SECRET")
    LIFETIME_YEARLY_LOOKUP_KEYS = SETTINGS.get("LIFETIME_YEARLY_LOOKUP_KEYS", "")
    LIFETIME_COUPON_CODES = SETTINGS.get("LIFETIME_COUPON_CODES", "")
    LIFETIME_COUPON_IDS = SETTINGS.get("LIFETIME_COUPON_IDS", "")
    LIFETIME_PROMOTION_CODE_IDS = SETTINGS.get("LIFETIME_PROMOTION_CODE_IDS", "")
    WHOP_API_KEY = SETTINGS.get("WHOP_API_KEY")
    WHOP_APP_ID = SETTINGS.get("WHOP_APP_ID")
    GOOGLE_OAUTH_CLIENT_ID = SETTINGS.get("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = SETTINGS.get("GOOGLE_OAUTH_CLIENT_SECRET")

    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': SETTINGS.get("SQLALCHEMY_POOL_SIZE", 15),
        'max_overflow': SETTINGS.get("SQLALCHEMY_MAX_OVERFLOW", 5),
        'pool_pre_ping': True,
        'pool_recycle': SETTINGS.get("SQLALCHEMY_POOL_RECYCLE", 900),
        'pool_timeout': SETTINGS.get("SQLALCHEMY_POOL_TIMEOUT", 15),
        'pool_use_lifo': SETTINGS.get("SQLALCHEMY_POOL_USE_LIFO", True),
        'pool_reset_on_return': SETTINGS.get("SQLALCHEMY_POOL_RESET_ON_RETURN", "commit") or "commit",
    }
    DB_STATEMENT_TIMEOUT_MS = SETTINGS.get("DB_STATEMENT_TIMEOUT_MS", 15000)
    DB_LOCK_TIMEOUT_MS = SETTINGS.get("DB_LOCK_TIMEOUT_MS", 5000)
    DB_IDLE_TX_TIMEOUT_MS = SETTINGS.get("DB_IDLE_TX_TIMEOUT_MS", 60000)

    BILLING_CACHE_ENABLED = SETTINGS.get("BILLING_CACHE_ENABLED", True)
    BILLING_GATE_CACHE_TTL_SECONDS = SETTINGS.get("BILLING_GATE_CACHE_TTL_SECONDS", 60)

    FEATURE_INVENTORY_ANALYTICS = SETTINGS.get("FEATURE_INVENTORY_ANALYTICS", True)
    FEATURE_BATCHBOT = SETTINGS.get("FEATURE_BATCHBOT", True)

    GOOGLE_AI_API_KEY = SETTINGS.get("GOOGLE_AI_API_KEY")
    GOOGLE_AI_DEFAULT_MODEL = SETTINGS.get("GOOGLE_AI_DEFAULT_MODEL") or "gemini-1.5-flash"
    GOOGLE_AI_BATCHBOT_MODEL = SETTINGS.get("GOOGLE_AI_BATCHBOT_MODEL") or GOOGLE_AI_DEFAULT_MODEL or "gemini-1.5-pro"
    GOOGLE_AI_PUBLICBOT_MODEL = SETTINGS.get("GOOGLE_AI_PUBLICBOT_MODEL") or "gemini-1.5-flash"
    GOOGLE_AI_ENABLE_SEARCH = SETTINGS.get("GOOGLE_AI_ENABLE_SEARCH", True)
    GOOGLE_AI_ENABLE_FILE_SEARCH = SETTINGS.get("GOOGLE_AI_ENABLE_FILE_SEARCH", True)
    GOOGLE_AI_SEARCH_TOOL = SETTINGS.get("GOOGLE_AI_SEARCH_TOOL") or "google_search"
    BATCHBOT_REQUEST_TIMEOUT_SECONDS = SETTINGS.get("BATCHBOT_REQUEST_TIMEOUT_SECONDS", 45)
    BATCHBOT_DEFAULT_MAX_REQUESTS = SETTINGS.get("BATCHBOT_DEFAULT_MAX_REQUESTS", 0)
    BATCHBOT_REQUEST_WINDOW_DAYS = SETTINGS.get("BATCHBOT_REQUEST_WINDOW_DAYS", 30)
    BATCHBOT_CHAT_MAX_MESSAGES = SETTINGS.get("BATCHBOT_CHAT_MAX_MESSAGES", 60)
    BATCHBOT_COST_PER_MILLION_INPUT = SETTINGS.get("BATCHBOT_COST_PER_MILLION_INPUT", 0.35)
    BATCHBOT_COST_PER_MILLION_OUTPUT = SETTINGS.get("BATCHBOT_COST_PER_MILLION_OUTPUT", 0.53)
    BATCHBOT_SIGNUP_BONUS_REQUESTS = SETTINGS.get("BATCHBOT_SIGNUP_BONUS_REQUESTS", 20)
    BATCHBOT_REFILL_LOOKUP_KEY = SETTINGS.get("BATCHBOT_REFILL_LOOKUP_KEY") or "batchbot_refill_100"

    DOMAIN_EVENT_WEBHOOK_URL = SETTINGS.get("DOMAIN_EVENT_WEBHOOK_URL")


# --- DevelopmentConfig ---
# Purpose: Override settings for local development defaults.
class DevelopmentConfig(BaseConfig):
    ENV = 'development'
    DEBUG = True
    DEVELOPMENT = True
    SESSION_COOKIE_SECURE = False

    _db_url = _normalize_db_url(SETTINGS.get("DATABASE_URL"))
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


# --- TestingConfig ---
# Purpose: Override settings for tests and in-memory databases.
class TestingConfig(BaseConfig):
    ENV = 'testing'
    TESTING = True
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
    }
    RATELIMIT_STORAGE_URI = SETTINGS.get("RATELIMIT_STORAGE_URI") or 'memory://'
    RATELIMIT_STORAGE_URL = RATELIMIT_STORAGE_URI
    SESSION_TYPE = 'filesystem'


# --- StagingConfig ---
# Purpose: Override settings for staging deployments.
class StagingConfig(BaseConfig):
    ENV = 'staging'
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(SETTINGS.get("DATABASE_URL"))


# --- ProductionConfig ---
# Purpose: Override settings for production deployments.
class ProductionConfig(BaseConfig):
    ENV = 'production'
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = 'https'
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(SETTINGS.get("DATABASE_URL"))


config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
}


# --- Active config name ---
# Purpose: Return the resolved environment name.
def get_active_config_name() -> str:
    return ENV_INFO.name


# --- Get config ---
# Purpose: Return the config class for the active environment.
def get_config():
    return config_map[get_active_config_name()]


Config = config_map[ENV_INFO.name]
ENV_DIAGNOSTICS = {
    'active': ENV_INFO.name,
    'source': ENV_INFO.source,
    'variables': {ENV_INFO.source: ENV_INFO.raw_value},
    'warnings': tuple(env.warnings),
}
