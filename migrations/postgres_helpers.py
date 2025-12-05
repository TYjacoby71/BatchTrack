"""
Cross-dialect (PostgreSQL + SQLite) migration helpers.

These utilities provide safe, idempotent operations that work across
both PostgreSQL and SQLite, minimizing ALTER-in-place usage and
handling differences like constraints and functional/GIN indexes.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterable

from alembic import op
from sqlalchemy import inspect, text
import sqlalchemy as sa # Import sqlalchemy

logger = logging.getLogger("alembic.helpers")


# --------------- Dialect detection ---------------
def _bind():
    return op.get_bind()


def is_sqlite() -> bool:
    conn = _bind()
    return "sqlite" in str(conn.engine.url)


def is_postgresql() -> bool:
    try:
        conn = _bind()
        dialect_name = str(conn.engine.url.drivername).lower()
        return any(pg in dialect_name for pg in ['postgresql', 'postgres', 'psycopg'])
    except Exception:
        return False


def _inspector():
    return inspect(_bind())


# --------------- SQLite temp table cleanup ---------------
def clean_sqlite_temp_tables() -> None:
    if not is_sqlite():
        return
    conn = _bind()
    try:
        result = conn.execute(
            text(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name LIKE '_alembic_tmp_%'
                """
            )
        )
        temp_tables = [row[0] for row in result.fetchall()]
        for table_name in temp_tables:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                logger.info(f"   ✅ Cleaned: {table_name}")
            except Exception as e:  # pragma: no cover - best effort
                logger.warning(f"   ⚠️  Failed to clean {table_name}: {e}")
        if temp_tables:
            conn.commit()
    except Exception as e:  # pragma: no cover - best effort
        logger.warning(f"⚠️  Could not clean temporary tables: {e}")


@contextmanager
def safe_batch_alter_table(table_name: str, **kwargs):
    clean_sqlite_temp_tables()
    try:
        with op.batch_alter_table(table_name, **kwargs) as batch_op:
            yield batch_op
    except Exception as e:
        if is_sqlite():
            logger.warning(f"Batch operation failed, cleaning temporary tables: {e}")
            clean_sqlite_temp_tables()
        raise


# --------------- Existence checks ---------------
def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    try:
        inspector = sa.inspect(op.get_bind())
        return inspector.has_table(table_name)
    except Exception:
        return False


def constraint_exists(table_name: str, constraint_name: str) -> bool:
    """Check if a constraint exists on a table."""
    try:
        inspector = sa.inspect(op.get_bind())
        # Check for foreign keys specifically
        foreign_keys = inspector.get_foreign_keys(table_name)
        if any(fk.get('name') == constraint_name for fk in foreign_keys):
            return True
        # Check for unique constraints
        unique_constraints = inspector.get_unique_constraints(table_name)
        if any(uc.get('name') == constraint_name for uc in unique_constraints):
            return True
        # Check for primary key constraints
        pk_constraint = inspector.get_pk_constraint(table_name)
        if pk_constraint.get('name') == constraint_name:
            return True
        # Check for indexes (which can also be unique constraints)
        indexes = inspector.get_indexes(table_name)
        if any(idx.get('name') == constraint_name for idx in indexes):
            return True
        return False
    except Exception:
        return False


def column_exists(table_name: str, column_name: str) -> bool:
    if not table_exists(table_name):
        return False
    try:
        cols = [c["name"] for c in _inspector().get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def index_exists(table_name: str, index_name: str) -> bool:
    if not table_exists(table_name):
        return False
    try:
        # Try portable inspector first
        for idx in _inspector().get_indexes(table_name):
            name = idx.get("name") or idx.get("indexname")
            if name == index_name:
                return True
        # Fallback to PG catalogs
        if is_postgresql():
            res = _bind().execute(
                text(
                    """
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = :t AND indexname = :i
                    """
                ),
                {"t": table_name, "i": index_name},
            )
            return res.first() is not None
        # Fallback to SQLite sqlite_master
        if is_sqlite():
            res = _bind().execute(
                text(
                    "SELECT 1 FROM sqlite_master WHERE type='index' AND name = :i"
                ),
                {"i": index_name},
            )
            return res.first() is not None
    except Exception:
        return False
    return False


def unique_constraint_exists(table_name: str, constraint_name: str) -> bool:
    if not table_exists(table_name):
        return False
    try:
        # Inspector path
        try:
            for uq in _inspector().get_unique_constraints(table_name):
                if uq.get("name") == constraint_name:
                    return True
        except Exception:
            pass
        # Fallback to PG information_schema
        if is_postgresql():
            res = _bind().execute(
                text(
                    """
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_name = :t AND constraint_name = :c
                    """
                ),
                {"t": table_name, "c": constraint_name},
            )
            return res.first() is not None
    except Exception:
        return False
    return False


# --------------- Safe DDL operations ---------------
def safe_add_column(table_name: str, column_def, verbose: bool = True) -> bool:
    if not table_exists(table_name):
        if verbose:
            print(f"   ⚠️  {table_name} table does not exist - skipping column add")
        return False
    col_name = column_def.name
    if column_exists(table_name, col_name):
        if verbose:
            # keep quiet to reduce noisy logs
            pass
        return False
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(column_def)
        if verbose:
            print(f"   ✅ {col_name} column added successfully")
        return True
    except Exception as e:
        if verbose:
            print(f"   ❌ Failed to add {col_name} column: {e}")
        raise


def safe_drop_column(table_name: str, column_name: str, verbose: bool = True) -> bool:
    if not column_exists(table_name, column_name):
        return False
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column(column_name)
        if verbose:
            print(f"✅ Dropped {column_name} from {table_name}")
        return True
    except Exception as e:
        if verbose:
            print(f"⚠️  Error dropping {column_name} from {table_name}: {e}")
        return False


def safe_create_index(
    index_name: str, table_name: str, columns: Iterable[str], unique: bool = False, verbose: bool = True
) -> bool:
    if not table_exists(table_name):
        return False
    for col in columns:
        if not column_exists(table_name, col):
            return False
    if index_exists(table_name, index_name):
        return False
    try:
        op.create_index(index_name, table_name, list(columns), unique=unique)
        if verbose:
            print(f"   ✅ Created index {index_name} on {table_name}")
        return True
    except Exception as e:
        if verbose:
            print(f"   ⚠️  Error creating index {index_name}: {e}")
        return False


def safe_drop_index(index_name: str, table_name: str | None = None, verbose: bool = True) -> bool:
    try:
        if table_name and not index_exists(table_name, index_name):
            return False
        op.drop_index(index_name, table_name=table_name) if table_name else op.drop_index(index_name)
        if verbose:
            print(f"✅ Dropped index {index_name}")
        return True
    except Exception as e:
        if verbose:
            print(f"Index {index_name} doesn't exist or error: {e}")
        return False


def ensure_unique_constraint_or_index(
    table_name: str, constraint_name: str, columns: Iterable[str], verbose: bool = True
) -> bool:
    """Create a unique constraint if possible; otherwise create a unique index.

    Returns True only if something was created.
    """
    if not table_exists(table_name):
        return False
    if unique_constraint_exists(table_name, constraint_name):
        return False
    if index_exists(table_name, constraint_name):
        # If a unique index with the same name already exists, treat as done
        return False
    try:
        if is_postgresql():
            op.create_unique_constraint(constraint_name, table_name, list(columns))
        else:
            # SQLite: emulate via unique index on expression-free columns
            op.create_index(constraint_name, table_name, list(columns), unique=True)
        if verbose:
            print(f"   ✅ Created unique {'constraint' if is_postgresql() else 'index'} {constraint_name}")
        return True
    except Exception as e:
        if verbose:
            print(f"   ⚠️  Could not create unique constraint/index {constraint_name}: {e}")
        return False


def safe_create_foreign_key(
    fk_name: str,
    source_table: str,
    referent_table: str,
    local_cols: Iterable[str],
    remote_cols: Iterable[str],
    ondelete: str | None = None,
    verbose: bool = True,
) -> bool:
    if not table_exists(source_table) or not table_exists(referent_table):
        return False
    if is_sqlite():
        # SQLite cannot ALTER TABLE to add FKs without table rebuild; skip safely
        return False
    # Check if the foreign key already exists
    if constraint_exists(source_table, fk_name):
        if verbose:
            print(f"   ℹ️ Foreign key {fk_name} already exists on {source_table}")
        return False
    try:
        op.create_foreign_key(fk_name, source_table, referent_table, list(local_cols), list(remote_cols), ondelete=ondelete)
        if verbose:
            print(f"   ✅ Created foreign key {fk_name}")
        return True
    except Exception as e:
        if verbose:
            print(f"   ⚠️  Could not create foreign key {fk_name}: {e}")
        return False


def safe_drop_foreign_key(fk_name: str, table_name: str, verbose: bool = True) -> bool:
    """Safely drop a foreign key constraint if it exists"""
    if not table_exists(table_name):
        return False
    if is_sqlite():
        # SQLite doesn't support dropping individual foreign keys
        return False
    # Check if the foreign key exists before trying to drop
    if not constraint_exists(table_name, fk_name):
        if verbose:
            print(f"   ℹ️ Foreign key {fk_name} does not exist on {table_name}, skipping drop.")
        return False
    try:
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
        if verbose:
            print(f"✅ Dropped foreign key {fk_name}")
        return True
    except Exception as e:
        if verbose:
            print(f"⚠️ Foreign key {fk_name} doesn't exist or error: {e}")
        return False


def safe_alter_set_not_null(table_name: str, column_name: str, existing_type=None, verbose: bool = True) -> bool:
    """Best-effort NOT NULL enforcement.

    On SQLite this may require a table copy; batch_alter_table usually handles it,
    but if it fails we skip.
    """
    if not column_exists(table_name, column_name):
        return False
    try:
        op.alter_column(table_name, column_name, existing_type=existing_type, nullable=False)
        if verbose:
            print(f"   ✅ Set {table_name}.{column_name} NOT NULL")
        return True
    except Exception as e:
        if verbose:
            print(f"   ⚠️  Could not set NOT NULL on {table_name}.{column_name}: {e}")
        return False