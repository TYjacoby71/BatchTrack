"""Canonical configuration schema and helpers.

Synopsis:
Defines all supported configuration keys, defaults, and validation helpers.

Glossary:
- Schema: Canonical definition of config keys and metadata.
- Field: Single configuration variable definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


# --- ConfigField ---
# Purpose: Define the metadata and defaults for one config key.
@dataclass(frozen=True)
class ConfigField:
    key: str
    cast: str
    default: Any
    description: str
    section: str
    required: bool = False
    required_in: tuple[str, ...] = ()
    recommended: str | None = None
    secret: bool = False
    note: str | None = None
    include_in_docs: bool = True
    include_in_checklist: bool = True
    default_by_env: dict[str, Any] | None = None

    def default_for_env(self, env_name: str) -> Any:
        if self.default_by_env and env_name in self.default_by_env:
            return self.default_by_env[env_name]
        return self.default

    def is_required(self, env_name: str) -> bool:
        return self.required or (self.required_in and env_name in self.required_in)


# --- ConfigSection ---
# Purpose: Group config fields into a named checklist section.
@dataclass(frozen=True)
class ConfigSection:
    key: str
    title: str
    note: str | None
    fields: tuple[ConfigField, ...]


# --- ResolvedField ---
# Purpose: Capture resolved config values with source metadata.
@dataclass(frozen=True)
class ResolvedField:
    field: ConfigField
    value: Any
    source: str
    present: bool
    required: bool


DEPRECATED_ENV_KEYS: dict[str, str] = {
    "WEB_CONCURRENCY": "GUNICORN_WORKERS",
    "WORKERS": "GUNICORN_WORKERS",
    "DATABASE_INTERNAL_URL": "DATABASE_URL",
    "RATELIMIT_STORAGE_URL": "RATELIMIT_STORAGE_URI",
    "CACHE_REDIS_URL": "REDIS_URL",
    "GOOGLE_GENERATIVE_AI_API_KEY": "GOOGLE_AI_API_KEY",
    "ENV": "FLASK_ENV",
    "SECRET_KEY": "FLASK_SECRET_KEY",
    "FLASK_DEBUG": "Use LOG_LEVEL and the production logging config instead.",
}


# --- Parse string ---
# Purpose: Convert raw string values while honoring empty defaults.
def _parse_str(value: str | None, default: Any, *, allow_empty: bool = False) -> Any:
    if value is None:
        return default
    stripped = value.strip()
    if stripped == "" and not allow_empty:
        return default
    return stripped


# --- Parse integer ---
# Purpose: Convert raw string values into integers with fallback messaging.
def _parse_int(value: str | None, default: Any) -> tuple[Any, str | None]:
    if value is None or value.strip() == "":
        return default, None
    try:
        return int(value), None
    except ValueError:
        return default, "expected integer"


# --- Parse float ---
# Purpose: Convert raw string values into floats with fallback messaging.
def _parse_float(value: str | None, default: Any) -> tuple[Any, str | None]:
    if value is None or value.strip() == "":
        return default, None
    try:
        return float(value), None
    except ValueError:
        return default, "expected float"


# --- Parse boolean ---
# Purpose: Convert raw string values into booleans with fallback messaging.
def _parse_bool(value: str | None, default: Any) -> tuple[Any, str | None]:
    if value is None or value.strip() == "":
        return default, None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True, None
    if lowered in {"0", "false", "no", "off"}:
        return False, None
    return default, "expected boolean"


# --- Parse value ---
# Purpose: Dispatch raw values to the appropriate type parser.
def _parse_value(field: ConfigField, raw: str | None, default: Any) -> tuple[Any, str | None]:
    if field.cast == "int":
        return _parse_int(raw, default)
    if field.cast == "float":
        return _parse_float(raw, default)
    if field.cast == "bool":
        return _parse_bool(raw, default)
    return _parse_str(raw, default), None


# --- Resolve settings ---
# Purpose: Convert raw env values into typed config values and warnings.
def resolve_settings(env: Mapping[str, str], env_name: str) -> tuple[dict[str, Any], dict[str, ResolvedField], list[str]]:
    warnings: list[str] = []
    values: dict[str, Any] = {}
    resolved: dict[str, ResolvedField] = {}

    for field in CONFIG_FIELDS:
        raw = env.get(field.key)
        default = field.default_for_env(env_name)
        value, error = _parse_value(field, raw, default)
        source = "env" if raw not in (None, "") else "default"
        is_required = field.is_required(env_name)
        present = raw not in (None, "") if is_required else (raw not in (None, "") or value not in (None, ""))
        if error:
            warnings.append(f"{field.key} {error}; falling back to {default!r}.")
        if is_required and raw in (None, ""):
            warnings.append(f"{field.key} is required but missing.")

        values[field.key] = value
        resolved[field.key] = ResolvedField(
            field=field,
            value=value,
            source=source,
            present=present,
            required=is_required,
        )

    for key, replacement in DEPRECATED_ENV_KEYS.items():
        if env.get(key) not in (None, ""):
            warnings.append(f"{key} is deprecated; use {replacement} instead.")

    return values, resolved, warnings


# --- Iterate sections ---
# Purpose: Return the ordered config sections for docs and checklists.
def iter_sections() -> Iterable[ConfigSection]:
    return CONFIG_SECTIONS


# --- Build checklist sections ---
# Purpose: Transform schema fields into the integrations checklist payload.
def build_integration_sections(env: Mapping[str, str], env_name: str) -> list[dict[str, Any]]:
    _, resolved, _ = resolve_settings(env, env_name)
    sections: list[dict[str, Any]] = []
    for section in CONFIG_SECTIONS:
        rows = []
        for field in section.fields:
            if not field.include_in_checklist:
                continue
            resolved_field = resolved[field.key]
            rows.append(
                {
                    "category": section.title,
                    "key": field.key,
                    "present": resolved_field.present,
                    "required": resolved_field.required,
                    "recommended": field.recommended,
                    "description": field.description,
                    "note": field.note,
                    "is_secret": field.secret,
                    "source": resolved_field.source,
                    "allow_config": not resolved_field.required,
                }
            )
        sections.append({"title": section.title, "note": section.note, "rows": rows})
    return sections


# --- Field helper ---
# Purpose: Build ConfigField instances with shared defaults.
def _field(
    key: str,
    cast: str,
    default: Any,
    description: str,
    section: str,
    *,
    required: bool = False,
    required_in: tuple[str, ...] = (),
    recommended: str | None = None,
    secret: bool = False,
    note: str | None = None,
    include_in_docs: bool = True,
    include_in_checklist: bool = True,
    default_by_env: dict[str, Any] | None = None,
) -> ConfigField:
    return ConfigField(
        key=key,
        cast=cast,
        default=default,
        description=description,
        section=section,
        required=required,
        required_in=required_in,
        recommended=recommended,
        secret=secret,
        note=note,
        include_in_docs=include_in_docs,
        include_in_checklist=include_in_checklist,
        default_by_env=default_by_env,
    )


_SECTION_CORE = "core"
_SECTION_DB = "database"
_SECTION_CACHE = "cache"
_SECTION_SECURITY = "security"
_SECTION_EMAIL = "email"
_SECTION_BILLING = "billing"
_SECTION_AI = "ai"
_SECTION_OAUTH = "oauth"
_SECTION_LOAD = "load"
_SECTION_GUNICORN = "gunicorn"
_SECTION_FEATURES = "features"
_SECTION_OPS = "operations"


CONFIG_FIELDS: tuple[ConfigField, ...] = (
    _field(
        "FLASK_ENV",
        "str",
        "development",
        "Runtime environment selector.",
        _SECTION_CORE,
        required=True,
        recommended="production",
        note="Allowed values: development, testing, staging, production.",
    ),
    _field(
        "FLASK_SECRET_KEY",
        "str",
        None,
        "Flask session signing secret.",
        _SECTION_CORE,
        required=True,
        secret=True,
        recommended="your-secret-key-here-must-be-32-chars-minimum",
        default_by_env={
            "development": "devkey-please-change-in-production",
            "testing": "devkey-please-change-in-production",
        },
    ),
    _field(
        "APP_BASE_URL",
        "str",
        None,
        "Canonical public base URL (https://app.example.com).",
        _SECTION_CORE,
        required_in=("staging", "production"),
        recommended="https://app.example.com",
        default_by_env={"development": "http://localhost:5000", "testing": "http://localhost:5000"},
    ),
    _field(
        "APP_HOST",
        "str",
        None,
        "Optional explicit host override for proxy/CSRF checks.",
        _SECTION_CORE,
        required=False,
        recommended="app.example.com",
    ),
    _field(
        "LOG_LEVEL",
        "str",
        "WARNING",
        "Application logging level.",
        _SECTION_CORE,
        required=False,
        recommended="INFO",
        default_by_env={"staging": "INFO", "production": "INFO"},
    ),
    _field(
        "ANON_REQUEST_LOG_LEVEL",
        "str",
        "DEBUG",
        "Anonymous request log level override.",
        _SECTION_CORE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "ALLOW_DEV_SERVER_IN_PRODUCTION",
        "bool",
        False,
        "Allow running the Flask dev server in production.",
        _SECTION_CORE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "LOG_REDACT_PII",
        "bool",
        True,
        "Enable PII redaction in logs.",
        _SECTION_CORE,
        required=False,
        recommended="true",
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "DATABASE_URL",
        "str",
        None,
        "Primary database connection string.",
        _SECTION_DB,
        required_in=("staging", "production"),
        secret=True,
        recommended="postgresql://user:password@host:5432/batchtrack",
    ),
    _field(
        "SQLALCHEMY_CREATE_ALL",
        "bool",
        False,
        "Run db.create_all() during startup.",
        _SECTION_DB,
        required=False,
        recommended="0",
        note="Set to 1 for local seeding only.",
    ),
    _field(
        "SQLALCHEMY_POOL_SIZE",
        "int",
        15,
        "SQLAlchemy connection pool size (per worker).",
        _SECTION_DB,
        required=False,
        recommended="20",
        default_by_env={"staging": 20, "production": 20, "testing": 5},
    ),
    _field(
        "SQLALCHEMY_MAX_OVERFLOW",
        "int",
        5,
        "Additional connections allowed past pool_size.",
        _SECTION_DB,
        required=False,
        recommended="20",
        default_by_env={"staging": 20, "production": 20, "testing": 5},
    ),
    _field(
        "SQLALCHEMY_POOL_TIMEOUT",
        "int",
        15,
        "Seconds to wait for a DB connection before failing.",
        _SECTION_DB,
        required=False,
        recommended="45",
        default_by_env={"staging": 45, "production": 45, "testing": 15},
    ),
    _field(
        "SQLALCHEMY_POOL_RECYCLE",
        "int",
        900,
        "Seconds before recycling idle DB connections.",
        _SECTION_DB,
        required=False,
        recommended="1800",
        default_by_env={"staging": 1800, "production": 1800, "testing": 3600},
    ),
    _field(
        "SQLALCHEMY_POOL_USE_LIFO",
        "bool",
        True,
        "Prefer most recently used connections in the pool.",
        _SECTION_DB,
        required=False,
        recommended="true",
    ),
    _field(
        "SQLALCHEMY_POOL_RESET_ON_RETURN",
        "str",
        "commit",
        "Reset behavior when returning a connection to the pool.",
        _SECTION_DB,
        required=False,
        recommended="commit",
    ),
    _field(
        "DB_STATEMENT_TIMEOUT_MS",
        "int",
        15000,
        "Statement timeout in milliseconds.",
        _SECTION_DB,
        required=False,
        recommended="15000",
    ),
    _field(
        "DB_LOCK_TIMEOUT_MS",
        "int",
        5000,
        "Lock acquisition timeout in milliseconds.",
        _SECTION_DB,
        required=False,
        recommended="5000",
    ),
    _field(
        "DB_IDLE_TX_TIMEOUT_MS",
        "int",
        60000,
        "Idle-in-transaction timeout in milliseconds.",
        _SECTION_DB,
        required=False,
        recommended="60000",
    ),
    _field(
        "REDIS_URL",
        "str",
        None,
        "Redis connection string.",
        _SECTION_CACHE,
        required_in=("staging", "production"),
        secret=True,
        recommended="redis://user:password@host:6379/0",
    ),
    _field(
        "SESSION_TYPE",
        "str",
        "redis",
        "Server-side session backend.",
        _SECTION_CACHE,
        required=False,
        recommended="redis",
    ),
    _field(
        "SESSION_LIFETIME_MINUTES",
        "int",
        60,
        "Session lifetime in minutes.",
        _SECTION_CACHE,
        required=False,
        recommended="60",
    ),
    _field(
        "CACHE_TYPE",
        "str",
        "SimpleCache",
        "Cache backend.",
        _SECTION_CACHE,
        required=False,
        recommended="RedisCache",
        default_by_env={"staging": "RedisCache", "production": "RedisCache"},
    ),
    _field(
        "CACHE_DEFAULT_TIMEOUT",
        "int",
        120,
        "Default cache TTL in seconds.",
        _SECTION_CACHE,
        required=False,
        recommended="120",
    ),
    _field(
        "INGREDIENT_LIST_CACHE_TTL",
        "int",
        120,
        "Ingredient list cache TTL in seconds.",
        _SECTION_CACHE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "RECIPE_LIST_CACHE_TTL",
        "int",
        180,
        "Recipe list cache TTL in seconds.",
        _SECTION_CACHE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "RECIPE_LIST_PAGE_SIZE",
        "int",
        10,
        "Recipe list page size.",
        _SECTION_CACHE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "PRODUCT_LIST_CACHE_TTL",
        "int",
        180,
        "Product list cache TTL in seconds.",
        _SECTION_CACHE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "GLOBAL_LIBRARY_CACHE_TTL",
        "int",
        300,
        "Global library cache TTL in seconds.",
        _SECTION_CACHE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "RECIPE_LIBRARY_CACHE_TTL",
        "int",
        180,
        "Recipe library cache TTL in seconds.",
        _SECTION_CACHE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "RECIPE_FORM_CACHE_TTL",
        "int",
        60,
        "Recipe form cache TTL in seconds.",
        _SECTION_CACHE,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "REDIS_MAX_CONNECTIONS",
        "int",
        None,
        "Max clients allowed by your Redis plan.",
        _SECTION_CACHE,
        required=False,
        recommended="250",
        note="Set to your plan limit (example: 250).",
    ),
    _field(
        "REDIS_POOL_MAX_CONNECTIONS",
        "int",
        None,
        "Shared Redis connection pool size (per worker).",
        _SECTION_CACHE,
        required=False,
        recommended="20",
        note="Per-worker hard cap (optional).",
    ),
    _field(
        "REDIS_POOL_TIMEOUT",
        "int",
        5,
        "Seconds to wait for a Redis connection before erroring.",
        _SECTION_CACHE,
        required=False,
        recommended="5",
    ),
    _field(
        "REDIS_SOCKET_TIMEOUT",
        "int",
        5,
        "Redis socket timeout in seconds.",
        _SECTION_CACHE,
        required=False,
        recommended="5",
    ),
    _field(
        "REDIS_CONNECT_TIMEOUT",
        "int",
        5,
        "Redis connect timeout in seconds.",
        _SECTION_CACHE,
        required=False,
        recommended="5",
    ),
    _field(
        "RATELIMIT_STORAGE_URI",
        "str",
        None,
        "Rate limiter storage URI (defaults to REDIS_URL).",
        _SECTION_CACHE,
        required=False,
        recommended="redis://user:password@host:6379/0",
    ),
    _field(
        "RATELIMIT_ENABLED",
        "bool",
        True,
        "Enable rate limiting middleware.",
        _SECTION_CACHE,
        required=False,
        recommended="true",
    ),
    _field(
        "RATELIMIT_DEFAULT",
        "str",
        "5000 per hour;1000 per minute",
        "Default rate limit string.",
        _SECTION_CACHE,
        required=False,
        recommended="5000 per hour;1000 per minute",
    ),
    _field(
        "RATELIMIT_SWALLOW_ERRORS",
        "bool",
        True,
        "Allow requests to proceed when rate limit backend fails.",
        _SECTION_CACHE,
        required=False,
        recommended="true",
    ),
    _field(
        "ENABLE_PROXY_FIX",
        "bool",
        False,
        "Wrap the app in Werkzeug ProxyFix.",
        _SECTION_SECURITY,
        required_in=("staging", "production"),
        recommended="true",
    ),
    _field(
        "TRUST_PROXY_HEADERS",
        "bool",
        True,
        "Legacy proxy header toggle.",
        _SECTION_SECURITY,
        required=False,
        recommended="true",
    ),
    _field(
        "PROXY_FIX_X_FOR",
        "int",
        1,
        "Number of X-Forwarded-For headers to trust.",
        _SECTION_SECURITY,
        required=False,
        recommended="1",
    ),
    _field(
        "PROXY_FIX_X_PROTO",
        "int",
        1,
        "Number of X-Forwarded-Proto headers to trust.",
        _SECTION_SECURITY,
        required=False,
        recommended="1",
    ),
    _field(
        "PROXY_FIX_X_HOST",
        "int",
        1,
        "Number of X-Forwarded-Host headers to trust.",
        _SECTION_SECURITY,
        required=False,
        recommended="1",
    ),
    _field(
        "PROXY_FIX_X_PORT",
        "int",
        1,
        "Number of X-Forwarded-Port headers to trust.",
        _SECTION_SECURITY,
        required=False,
        recommended="1",
    ),
    _field(
        "PROXY_FIX_X_PREFIX",
        "int",
        0,
        "Number of X-Forwarded-Prefix headers to trust.",
        _SECTION_SECURITY,
        required=False,
        recommended="0",
    ),
    _field(
        "FORCE_SECURITY_HEADERS",
        "bool",
        True,
        "Force security headers on every response.",
        _SECTION_SECURITY,
        required=False,
        recommended="true",
    ),
    _field(
        "DISABLE_SECURITY_HEADERS",
        "bool",
        False,
        "Disable security headers middleware.",
        _SECTION_SECURITY,
        required=False,
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "EMAIL_PROVIDER",
        "str",
        "smtp",
        "Email provider selector.",
        _SECTION_EMAIL,
        required=False,
        recommended="smtp",
    ),
    _field(
        "MAIL_SERVER",
        "str",
        "smtp.gmail.com",
        "SMTP server hostname.",
        _SECTION_EMAIL,
        required=False,
        recommended="smtp.your-provider.com",
    ),
    _field(
        "MAIL_PORT",
        "int",
        587,
        "SMTP server port.",
        _SECTION_EMAIL,
        required=False,
        recommended="587",
    ),
    _field(
        "MAIL_USE_TLS",
        "bool",
        True,
        "Enable TLS for SMTP.",
        _SECTION_EMAIL,
        required=False,
        recommended="true",
    ),
    _field(
        "MAIL_USE_SSL",
        "bool",
        False,
        "Enable SSL for SMTP.",
        _SECTION_EMAIL,
        required=False,
        recommended="false",
    ),
    _field(
        "MAIL_USERNAME",
        "str",
        None,
        "SMTP username.",
        _SECTION_EMAIL,
        required=False,
        secret=True,
    ),
    _field(
        "MAIL_PASSWORD",
        "str",
        None,
        "SMTP password.",
        _SECTION_EMAIL,
        required=False,
        secret=True,
    ),
    _field(
        "MAIL_DEFAULT_SENDER",
        "str",
        "noreply@batchtrack.app",
        "Default email sender address.",
        _SECTION_EMAIL,
        required=False,
        recommended="noreply@batchtrack.app",
    ),
    _field(
        "SENDGRID_API_KEY",
        "str",
        None,
        "SendGrid API key.",
        _SECTION_EMAIL,
        required=False,
        secret=True,
    ),
    _field(
        "POSTMARK_SERVER_TOKEN",
        "str",
        None,
        "Postmark server token.",
        _SECTION_EMAIL,
        required=False,
        secret=True,
    ),
    _field(
        "MAILGUN_API_KEY",
        "str",
        None,
        "Mailgun API key.",
        _SECTION_EMAIL,
        required=False,
        secret=True,
    ),
    _field(
        "MAILGUN_DOMAIN",
        "str",
        None,
        "Mailgun domain.",
        _SECTION_EMAIL,
        required=False,
    ),
    _field(
        "STRIPE_PUBLISHABLE_KEY",
        "str",
        None,
        "Stripe publishable key.",
        _SECTION_BILLING,
        required=False,
        secret=True,
    ),
    _field(
        "STRIPE_SECRET_KEY",
        "str",
        None,
        "Stripe secret key.",
        _SECTION_BILLING,
        required=False,
        secret=True,
    ),
    _field(
        "STRIPE_WEBHOOK_SECRET",
        "str",
        None,
        "Stripe webhook secret.",
        _SECTION_BILLING,
        required=False,
        secret=True,
    ),
    _field(
        "BILLING_CACHE_ENABLED",
        "bool",
        True,
        "Enable billing cache.",
        _SECTION_BILLING,
        required=False,
        recommended="true",
    ),
    _field(
        "BILLING_GATE_CACHE_TTL_SECONDS",
        "int",
        60,
        "Billing cache TTL in seconds.",
        _SECTION_BILLING,
        required=False,
        recommended="60",
    ),
    _field(
        "BILLING_STATUS_CACHE_TTL",
        "int",
        120,
        "Billing status cache TTL in seconds.",
        _SECTION_BILLING,
        required=False,
        recommended="120",
    ),
    _field(
        "FEATURE_INVENTORY_ANALYTICS",
        "bool",
        True,
        "Enable inventory analytics feature.",
        _SECTION_FEATURES,
        required=False,
        recommended="true",
    ),
    _field(
        "FEATURE_BATCHBOT",
        "bool",
        True,
        "Master toggle for BatchBot features.",
        _SECTION_FEATURES,
        required=False,
        recommended="true",
    ),
    _field(
        "GOOGLE_AI_API_KEY",
        "str",
        None,
        "Gemini API key used by BatchBot.",
        _SECTION_AI,
        required=False,
        secret=True,
    ),
    _field(
        "GOOGLE_AI_DEFAULT_MODEL",
        "str",
        "gemini-1.5-flash",
        "Fallback Gemini model.",
        _SECTION_AI,
        required=False,
        recommended="gemini-1.5-flash",
    ),
    _field(
        "GOOGLE_AI_BATCHBOT_MODEL",
        "str",
        None,
        "Model used by the paid BatchBot.",
        _SECTION_AI,
        required=False,
        recommended="gemini-1.5-pro",
    ),
    _field(
        "GOOGLE_AI_PUBLICBOT_MODEL",
        "str",
        "gemini-1.5-flash",
        "Model used by the public help bot.",
        _SECTION_AI,
        required=False,
        recommended="gemini-1.5-flash",
    ),
    _field(
        "GOOGLE_AI_ENABLE_SEARCH",
        "bool",
        True,
        "Enable Google Search grounding for prompts.",
        _SECTION_AI,
        required=False,
        recommended="true",
    ),
    _field(
        "GOOGLE_AI_ENABLE_FILE_SEARCH",
        "bool",
        True,
        "Enable file search for prompts.",
        _SECTION_AI,
        required=False,
        recommended="true",
    ),
    _field(
        "GOOGLE_AI_SEARCH_TOOL",
        "str",
        "google_search",
        "Search tool identifier.",
        _SECTION_AI,
        required=False,
        recommended="google_search",
    ),
    _field(
        "BATCHBOT_REQUEST_TIMEOUT_SECONDS",
        "int",
        45,
        "BatchBot request timeout.",
        _SECTION_AI,
        required=False,
        recommended="45",
    ),
    _field(
        "BATCHBOT_DEFAULT_MAX_REQUESTS",
        "int",
        0,
        "Base allowance per org per window.",
        _SECTION_AI,
        required=False,
        recommended="0",
    ),
    _field(
        "BATCHBOT_REQUEST_WINDOW_DAYS",
        "int",
        30,
        "BatchBot usage window length.",
        _SECTION_AI,
        required=False,
        recommended="30",
    ),
    _field(
        "BATCHBOT_CHAT_MAX_MESSAGES",
        "int",
        60,
        "Max chat-only prompts per window.",
        _SECTION_AI,
        required=False,
        recommended="60",
    ),
    _field(
        "BATCHBOT_COST_PER_MILLION_INPUT",
        "float",
        0.35,
        "Reference cost for inbound tokens (USD).",
        _SECTION_AI,
        required=False,
        recommended="0.35",
    ),
    _field(
        "BATCHBOT_COST_PER_MILLION_OUTPUT",
        "float",
        0.53,
        "Reference cost for outbound tokens (USD).",
        _SECTION_AI,
        required=False,
        recommended="0.53",
    ),
    _field(
        "BATCHBOT_SIGNUP_BONUS_REQUESTS",
        "int",
        20,
        "Bonus requests granted at signup.",
        _SECTION_AI,
        required=False,
        recommended="20",
    ),
    _field(
        "BATCHBOT_REFILL_LOOKUP_KEY",
        "str",
        "batchbot_refill_100",
        "Stripe lookup key for BatchBot refills.",
        _SECTION_AI,
        required=False,
        recommended="batchbot_refill_100",
    ),
    _field(
        "DOMAIN_EVENT_WEBHOOK_URL",
        "str",
        None,
        "Outbound webhook URL for domain events.",
        _SECTION_OPS,
        required=False,
        recommended="https://your-domain-event-endpoint.example",
    ),
    _field(
        "GOOGLE_OAUTH_CLIENT_ID",
        "str",
        None,
        "Google OAuth 2.0 client ID.",
        _SECTION_OAUTH,
        required=False,
        secret=True,
    ),
    _field(
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "str",
        None,
        "Google OAuth 2.0 client secret.",
        _SECTION_OAUTH,
        required=False,
        secret=True,
    ),
    _field(
        "WHOP_API_KEY",
        "str",
        None,
        "Whop API key.",
        _SECTION_OAUTH,
        required=False,
        secret=True,
    ),
    _field(
        "WHOP_APP_ID",
        "str",
        None,
        "Whop app ID.",
        _SECTION_OAUTH,
        required=False,
        secret=True,
    ),
    _field(
        "LOCUST_USER_BASE",
        "str",
        "loadtest_user",
        "Username prefix for generated test accounts.",
        _SECTION_LOAD,
        required=False,
        recommended="loadtest_user",
    ),
    _field(
        "LOCUST_USER_PASSWORD",
        "str",
        "loadtest123",
        "Password shared by generated load-test users.",
        _SECTION_LOAD,
        required=False,
        recommended="loadtest123",
        secret=True,
    ),
    _field(
        "LOCUST_USER_COUNT",
        "int",
        10000,
        "Number of sequential users to generate.",
        _SECTION_LOAD,
        required=False,
        recommended="500",
    ),
    _field(
        "LOCUST_CACHE_TTL",
        "int",
        120,
        "Seconds before Locust refreshes cached IDs.",
        _SECTION_LOAD,
        required=False,
        recommended="120",
    ),
    _field(
        "LOCUST_REQUIRE_HTTPS",
        "bool",
        True,
        "Require HTTPS host for Locust logins.",
        _SECTION_LOAD,
        required=False,
        recommended="1",
    ),
    _field(
        "LOCUST_LOG_LOGIN_FAILURE_CONTEXT",
        "bool",
        False,
        "Log structured auth.login failures.",
        _SECTION_LOAD,
        required=False,
        recommended="0",
    ),
    _field(
        "LOCUST_ENABLE_BROWSE_USERS",
        "bool",
        True,
        "Enable anonymous browse users in Locust.",
        _SECTION_LOAD,
        required=False,
        recommended="1",
    ),
    _field(
        "LOCUST_FAIL_FAST_LOGIN",
        "bool",
        True,
        "Abort user if login fails during Locust start.",
        _SECTION_LOAD,
        required=False,
        recommended="1",
    ),
    _field(
        "LOCUST_ABORT_ON_AUTH_FAILURE",
        "bool",
        False,
        "Stop user on auth failure during Locust runs.",
        _SECTION_LOAD,
        required=False,
        recommended="0",
    ),
    _field(
        "LOCUST_MAX_LOGIN_ATTEMPTS",
        "int",
        2,
        "Max login retries before aborting.",
        _SECTION_LOAD,
        required=False,
        recommended="2",
    ),
    _field(
        "LOCUST_USER_CREDENTIALS",
        "str",
        None,
        "JSON list of explicit username/password pairs.",
        _SECTION_LOAD,
        required=False,
        include_in_docs=True,
        include_in_checklist=True,
        note='Example: [{"username":"user1","password":"pass"}]',
    ),
    _field(
        "GUNICORN_WORKERS",
        "int",
        2,
        "Gunicorn worker count.",
        _SECTION_GUNICORN,
        required=False,
        recommended="2",
    ),
    _field(
        "GUNICORN_WORKER_CLASS",
        "str",
        "gevent",
        "Gunicorn worker class.",
        _SECTION_GUNICORN,
        required=False,
        recommended="gevent",
    ),
    _field(
        "GUNICORN_WORKER_CONNECTIONS",
        "int",
        2000,
        "Gunicorn worker connection limit.",
        _SECTION_GUNICORN,
        required=False,
        recommended="1000",
    ),
    _field(
        "GUNICORN_TIMEOUT",
        "int",
        60,
        "Gunicorn worker timeout in seconds.",
        _SECTION_GUNICORN,
        required=False,
        recommended="30",
    ),
    _field(
        "GUNICORN_KEEPALIVE",
        "int",
        5,
        "Gunicorn keepalive seconds.",
        _SECTION_GUNICORN,
        required=False,
        recommended="2",
    ),
    _field(
        "GUNICORN_MAX_REQUESTS",
        "int",
        2000,
        "Gunicorn max requests before recycle.",
        _SECTION_GUNICORN,
        required=False,
        recommended="2000",
    ),
    _field(
        "GUNICORN_MAX_REQUESTS_JITTER",
        "int",
        100,
        "Gunicorn max requests jitter.",
        _SECTION_GUNICORN,
        required=False,
        recommended="100",
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "GUNICORN_BACKLOG",
        "int",
        2048,
        "Gunicorn socket backlog.",
        _SECTION_GUNICORN,
        required=False,
        recommended="2048",
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "GUNICORN_LOG_LEVEL",
        "str",
        "info",
        "Gunicorn log level.",
        _SECTION_GUNICORN,
        required=False,
        recommended="info",
        include_in_docs=False,
        include_in_checklist=False,
    ),
    _field(
        "GUNICORN_PRELOAD_APP",
        "bool",
        False,
        "Preload the app before forking workers.",
        _SECTION_GUNICORN,
        required=False,
        recommended="0",
    ),
)


# --- Section field selector ---
# Purpose: Collect fields assigned to a given schema section.
def _section_fields(section_key: str) -> tuple[ConfigField, ...]:
    return tuple(field for field in CONFIG_FIELDS if field.section == section_key)


CONFIG_SECTIONS: tuple[ConfigSection, ...] = (
    ConfigSection(
        key=_SECTION_CORE,
        title="Core Runtime & Platform",
        note="Set these to lock the app into production mode before launch.",
        fields=_section_fields(_SECTION_CORE),
    ),
    ConfigSection(
        key=_SECTION_DB,
        title="Database & Persistence",
        note="Configure a managed Postgres instance before launch.",
        fields=_section_fields(_SECTION_DB),
    ),
    ConfigSection(
        key=_SECTION_CACHE,
        title="Caching & Rate Limits",
        note="Provision a managed Redis instance.",
        fields=_section_fields(_SECTION_CACHE),
    ),
    ConfigSection(
        key=_SECTION_SECURITY,
        title="Security & Networking",
        note="Enable proxy awareness and security headers behind your load balancer.",
        fields=_section_fields(_SECTION_SECURITY),
    ),
    ConfigSection(
        key=_SECTION_EMAIL,
        title="Email & Notifications",
        note="Configure exactly one provider for transactional email.",
        fields=_section_fields(_SECTION_EMAIL),
    ),
    ConfigSection(
        key=_SECTION_BILLING,
        title="Billing & Payments",
        note="Stripe and billing cache settings.",
        fields=_section_fields(_SECTION_BILLING),
    ),
    ConfigSection(
        key=_SECTION_FEATURES,
        title="Feature Flags",
        note="Optional feature toggles.",
        fields=_section_fields(_SECTION_FEATURES),
    ),
    ConfigSection(
        key=_SECTION_AI,
        title="AI Studio & BatchBot",
        note="Controls BatchBot models and quotas.",
        fields=_section_fields(_SECTION_AI),
    ),
    ConfigSection(
        key=_SECTION_OAUTH,
        title="OAuth & Marketplace",
        note="Optional integrations for SSO and marketplace licensing.",
        fields=_section_fields(_SECTION_OAUTH),
    ),
    ConfigSection(
        key=_SECTION_LOAD,
        title="Load Testing Inputs",
        note="Environment-driven knobs consumed by loadtests/locustfile.py.",
        fields=_section_fields(_SECTION_LOAD),
    ),
    ConfigSection(
        key=_SECTION_OPS,
        title="Operations & Webhooks",
        note="Optional operational integrations and webhook destinations.",
        fields=_section_fields(_SECTION_OPS),
    ),
    ConfigSection(
        key=_SECTION_GUNICORN,
        title="Gunicorn Server",
        note="Server process settings for Gunicorn.",
        fields=_section_fields(_SECTION_GUNICORN),
    ),
)
