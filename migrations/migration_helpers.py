from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Optional

from alembic import op
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


# --- Dialect helpers ---------------------------------------------------------

def get_connection() -> Connection:
    bind = op.get_bind()
    assert bind is not None, "Alembic op has no bind connection"
    return bind


def get_dialect_name() -> str:
    return get_connection().dialect.name


# --- SQLite cleanup helpers --------------------------------------------------

def sqlite_cleanup_temp_tables(verbose: bool = True) -> None:
    """Drop any SQLite temp/aux tables that may linger after failed batch ops.

    Safe to call on PostgreSQL (no-op). On SQLite, Alembic/SQLAlchemy batch
    migrations (ALTER TABLE emulation) can leave `sqlite_*_old` or
    `alembic_tmp_%` tables if an earlier run crashed. We remove those so a
    rerun can succeed.
    """
    dialect = get_dialect_name()
    if dialect != "sqlite":
        return

    conn = get_connection()
    inspector = inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # Common leftover table name patterns
    suspicious_prefixes = (
        "sqlite_",        # e.g., sqlite_autoindex_*
        "alembic_tmp_",   # temporary tables created by batch ops
        "tmp_",           # app-defined tmp tables
    )
    suspicious_suffixes = (
        "_old",           # old copy created during batch migrate
        "_backup",        # backups
    )

    to_drop: list[str] = []
    for table in existing_tables:
        if table.startswith(suspicious_prefixes) or table.endswith(suspicious_suffixes):
            to_drop.append(table)

    for table in sorted(to_drop):
        try:
            if verbose:
                print(f"🧹 Dropping leftover SQLite temp table: {table}")
            op.execute(text(f'DROP TABLE IF EXISTS "{table}"'))
        except Exception as exc:
            # Swallow and continue; we don't want cleanup to block upgrades
            if verbose:
                print(f"⚠️  Could not drop temp table {table}: {exc}")


# --- Existence checks --------------------------------------------------------

def table_exists(table_name: str) -> bool:
    inspector = inspect(get_connection())
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(table_name: str, column_name: str) -> bool:
    if not table_exists(table_name):
        return False
    inspector = inspect(get_connection())
    try:
        cols = [c['name'] for c in inspector.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def foreign_key_exists(table_name: str, fk_name: str) -> bool:
    if not table_exists(table_name):
        return False
    inspector = inspect(get_connection())
    try:
        fks = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in fks)
    except Exception:
        return False


# --- Safe ops ---------------------------------------------------------------

def safe_add_column(table_name: str, column_name: str, column_def):
    if not table_exists(table_name):
        print(f"   ⚠️  Table {table_name} does not exist - skipping {column_name}")
        return False
    if column_exists(table_name, column_name):
        print(f"   ✅ {column_name} already exists in {table_name}")
        return False
    try:
        op.add_column(table_name, column_def)
        print(f"   ✅ Added {column_name} to {table_name}")
        return True
    except Exception as exc:
        print(f"   ❌ Failed to add {column_name} to {table_name}: {exc}")
        raise


def safe_drop_column(table_name: str, column_name: str):
    if not table_exists(table_name):
        return False
    if not column_exists(table_name, column_name):
        return False
    try:
        op.drop_column(table_name, column_name)
        print(f"   ✅ Dropped {column_name} from {table_name}")
        return True
    except Exception as exc:
        print(f"   ⚠️  Could not drop {column_name} from {table_name}: {exc}")
        return False


def safe_create_foreign_key(constraint_name: str, source_table: str, referent_table: str,
                            local_cols: Iterable[str], remote_cols: Iterable[str], **kwargs):
    if foreign_key_exists(source_table, constraint_name):
        print(f"   ✅ Foreign key {constraint_name} already exists")
        return False
    try:
        op.create_foreign_key(constraint_name, source_table, referent_table, local_cols, remote_cols, **kwargs)
        print(f"   ✅ Created foreign key {constraint_name}")
        return True
    except Exception as exc:
        print(f"   ❌ Failed to create foreign key {constraint_name}: {exc}")
        raise


# --- Context manager to wrap upgrades with cleanup ---------------------------
@contextmanager
def with_sqlite_cleanup(verbose: bool = True):
    """Context manager that performs SQLite temp-table cleanup before block.

    Usage in migration upgrade():
        with with_sqlite_cleanup():
            ... safe ops ...
    """
    sqlite_cleanup_temp_tables(verbose=verbose)
    yield
