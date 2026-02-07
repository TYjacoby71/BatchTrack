"""Config schema: Cache and rate limit settings.

Synopsis:
Defines Redis, cache TTLs, and rate limiter configuration keys.

Glossary:
- Redis pool: Shared connection pool for Redis-backed features.
"""

# --- Cache fields ---
# Purpose: Provide cache, Redis, and rate limit configuration definitions.
FIELDS = [
    {
        "key": "REDIS_URL",
        "cast": "str",
        "default": None,
        "description": "Redis connection string.",
        "required_in": ("staging", "production"),
        "secret": True,
        "recommended": "redis://user:password@host:6379/0",
    },
    {
        "key": "SESSION_TYPE",
        "cast": "str",
        "default": "redis",
        "description": "Server-side session backend.",
        "recommended": "redis",
    },
    {
        "key": "SESSION_LIFETIME_MINUTES",
        "cast": "int",
        "default": 60,
        "description": "Session lifetime in minutes.",
        "recommended": "60",
    },
    {
        "key": "CACHE_TYPE",
        "cast": "str",
        "default": "SimpleCache",
        "description": "Cache backend.",
        "recommended": "RedisCache",
        "default_by_env": {"staging": "RedisCache", "production": "RedisCache"},
    },
    {
        "key": "CACHE_DEFAULT_TIMEOUT",
        "cast": "int",
        "default": 120,
        "description": "Default cache TTL in seconds.",
        "recommended": "120",
    },
    {
        "key": "INGREDIENT_LIST_CACHE_TTL",
        "cast": "int",
        "default": 120,
        "description": "Ingredient list cache TTL in seconds.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "RECIPE_LIST_CACHE_TTL",
        "cast": "int",
        "default": 180,
        "description": "Recipe list cache TTL in seconds.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "RECIPE_LIST_PAGE_SIZE",
        "cast": "int",
        "default": 10,
        "description": "Recipe list page size.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "PRODUCT_LIST_CACHE_TTL",
        "cast": "int",
        "default": 180,
        "description": "Product list cache TTL in seconds.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "GLOBAL_LIBRARY_CACHE_TTL",
        "cast": "int",
        "default": 300,
        "description": "Global library cache TTL in seconds.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "RECIPE_LIBRARY_CACHE_TTL",
        "cast": "int",
        "default": 180,
        "description": "Recipe library cache TTL in seconds.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "RECIPE_FORM_CACHE_TTL",
        "cast": "int",
        "default": 60,
        "description": "Recipe form cache TTL in seconds.",
        "include_in_docs": False,
        "include_in_checklist": False,
    },
    {
        "key": "REDIS_MAX_CONNECTIONS",
        "cast": "int",
        "default": None,
        "description": "Max clients allowed by your Redis plan.",
        "recommended": "250",
        "note": "Set to your plan limit (example: 250).",
    },
    {
        "key": "REDIS_POOL_MAX_CONNECTIONS",
        "cast": "int",
        "default": None,
        "description": "Shared Redis connection pool size (per worker).",
        "recommended": "20",
        "note": "Per-worker hard cap (optional).",
    },
    {
        "key": "REDIS_POOL_TIMEOUT",
        "cast": "int",
        "default": 5,
        "description": "Seconds to wait for a Redis connection before erroring.",
        "recommended": "5",
    },
    {
        "key": "REDIS_SOCKET_TIMEOUT",
        "cast": "int",
        "default": 5,
        "description": "Redis socket timeout in seconds.",
        "recommended": "5",
    },
    {
        "key": "REDIS_CONNECT_TIMEOUT",
        "cast": "int",
        "default": 5,
        "description": "Redis connect timeout in seconds.",
        "recommended": "5",
    },
    {
        "key": "RATELIMIT_STORAGE_URI",
        "cast": "str",
        "default": None,
        "description": "Rate limiter storage URI (defaults to REDIS_URL).",
        "recommended": "redis://user:password@host:6379/0",
    },
    {
        "key": "RATELIMIT_ENABLED",
        "cast": "bool",
        "default": True,
        "description": "Enable rate limiting middleware.",
        "recommended": "true",
    },
    {
        "key": "RATELIMIT_DEFAULT",
        "cast": "str",
        "default": "5000 per hour;1000 per minute",
        "description": "Default rate limit string.",
        "recommended": "5000 per hour;1000 per minute",
    },
    {
        "key": "RATELIMIT_SWALLOW_ERRORS",
        "cast": "bool",
        "default": True,
        "description": "Allow requests to proceed when rate limit backend fails.",
        "recommended": "true",
    },
]

# --- Cache section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "cache",
    "title": "Caching & Rate Limits",
    "note": "Provision a managed Redis instance.",
}
