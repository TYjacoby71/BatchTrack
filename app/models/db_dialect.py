"""Database dialect detection helpers.

Synopsis:
Infers the active database dialect based on configured SQLAlchemy URLs.

Glossary:
- Dialect: Database backend type (e.g., PostgreSQL, SQLite).
- Override: Environment variable used to force a specific value.
"""

import os
from typing import Final

_POSTGRES_PREFIXES: Final = (
    "postgres://",
    "postgresql://",
    "postgresql+psycopg2://",
)

_DIALECT_OVERRIDE_ENV: Final = "BATCHTRACK_FORCE_DB_DIALECT"
_DB_URL_OVERRIDE_ENV: Final = "BATCHTRACK_FORCE_DB_URL"


def _resolve_active_database_url() -> str:
    """Return the best-guess database URL based on environment precedence."""
    override = os.environ.get(_DB_URL_OVERRIDE_ENV)
    if override:
        return override

    precedence = (
        "SQLALCHEMY_TEST_DATABASE_URI",  # pytest / local overrides
        "SQLALCHEMY_DATABASE_URI",       # explicit SQLAlchemy config
        "DATABASE_URL",                  # canonical env var
    )

    for key in precedence:
        value = os.environ.get(key)
        if value:
            return value
    return ""


def _is_postgres_url(url: str | None) -> bool:
    if not url:
        return False
    lowered = url.strip().lower()
    return lowered.startswith(_POSTGRES_PREFIXES)


def is_postgres() -> bool:
    """Determine if the active database dialect is PostgreSQL.

    This favors explicit SQLAlchemy/Test overrides before falling back to
    DATABASE_URL, which prevents local pytest runs (sqlite) from inheriting a
    production Postgres URL that happens to be exported in the shell.
    """
    override = os.environ.get(_DIALECT_OVERRIDE_ENV)
    if override:
        normalized = override.strip().lower()
        return normalized in {"pg", "postgres", "postgresql"}

    return _is_postgres_url(_resolve_active_database_url())
