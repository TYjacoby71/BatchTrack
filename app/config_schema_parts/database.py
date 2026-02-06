"""Config schema: Database settings.

Synopsis:
Defines database connectivity and SQLAlchemy pool configuration keys.

Glossary:
- Pool: SQLAlchemy connection pool for database connections.
"""

# --- Database fields ---
# Purpose: Provide database configuration definitions and defaults.
FIELDS = [
    {
        "key": "DATABASE_URL",
        "cast": "str",
        "default": None,
        "description": "Primary database connection string.",
        "required_in": ("staging", "production"),
        "secret": True,
        "recommended": "postgresql://user:password@host:5432/batchtrack",
    },
    {
        "key": "SQLALCHEMY_CREATE_ALL",
        "cast": "bool",
        "default": False,
        "description": "Run db.create_all() during startup.",
        "recommended": "0",
        "note": "Set to 1 for local seeding only.",
    },
    {
        "key": "SQLALCHEMY_POOL_SIZE",
        "cast": "int",
        "default": 15,
        "description": "SQLAlchemy connection pool size (per worker).",
        "recommended": "20",
        "default_by_env": {"staging": 20, "production": 20, "testing": 5},
    },
    {
        "key": "SQLALCHEMY_MAX_OVERFLOW",
        "cast": "int",
        "default": 5,
        "description": "Additional connections allowed past pool_size.",
        "recommended": "20",
        "default_by_env": {"staging": 20, "production": 20, "testing": 5},
    },
    {
        "key": "SQLALCHEMY_POOL_TIMEOUT",
        "cast": "int",
        "default": 15,
        "description": "Seconds to wait for a DB connection before failing.",
        "recommended": "45",
        "default_by_env": {"staging": 45, "production": 45, "testing": 15},
    },
    {
        "key": "SQLALCHEMY_POOL_RECYCLE",
        "cast": "int",
        "default": 900,
        "description": "Seconds before recycling idle DB connections.",
        "recommended": "1800",
        "default_by_env": {"staging": 1800, "production": 1800, "testing": 3600},
    },
    {
        "key": "SQLALCHEMY_POOL_USE_LIFO",
        "cast": "bool",
        "default": True,
        "description": "Prefer most recently used connections in the pool.",
        "recommended": "true",
    },
    {
        "key": "SQLALCHEMY_POOL_RESET_ON_RETURN",
        "cast": "str",
        "default": "commit",
        "description": "Reset behavior when returning a connection to the pool.",
        "recommended": "commit",
    },
    {
        "key": "DB_STATEMENT_TIMEOUT_MS",
        "cast": "int",
        "default": 15000,
        "description": "Statement timeout in milliseconds.",
        "recommended": "15000",
    },
    {
        "key": "DB_LOCK_TIMEOUT_MS",
        "cast": "int",
        "default": 5000,
        "description": "Lock acquisition timeout in milliseconds.",
        "recommended": "5000",
    },
    {
        "key": "DB_IDLE_TX_TIMEOUT_MS",
        "cast": "int",
        "default": 60000,
        "description": "Idle-in-transaction timeout in milliseconds.",
        "recommended": "60000",
    },
]

# --- Database section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "database",
    "title": "Database & Persistence",
    "note": "Configure a managed Postgres instance before launch.",
}
