"""
PostgreSQL migration helpers for safe database operations.

This module provides utility functions to safely check for the existence
of database objects before attempting to create or drop them, preventing
transaction failures in PostgreSQL migrations.
"""
from alembic import op
from sqlalchemy import inspect, text


def table_exists(table_name):
    """Check if a table exists in the database.

    Args:
        table_name (str): Name of the table to check

    Returns:
        bool: True if table exists, False otherwise
    """
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(table_name, column_name):
    """Check if a column exists in a table.

    Args:
        table_name (str): Name of the table
        column_name (str): Name of the column to check

    Returns:
        bool: True if column exists, False otherwise
    """
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        print(f"   ⚠️  Error checking column {column_name} in {table_name}: {e}")
        return False


def index_exists(table_name, index_name):
    """Check if an index exists on a table.

    Args:
        table_name (str): Name of the table
        index_name (str): Name of the index to check

    Returns:
        bool: True if index exists, False otherwise
    """
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        result = bind.execute(text("""
            SELECT COUNT(*)
            FROM pg_indexes
            WHERE tablename = :table_name
            AND indexname = :index_name
        """), {"table_name": table_name, "index_name": index_name})
        return result.scalar() > 0
    except Exception:
        return False


def constraint_exists(table_name, constraint_name):
    """Check if a constraint exists on a table.

    Args:
        table_name (str): Name of the table
        constraint_name (str): Name of the constraint to check

    Returns:
        bool: True if constraint exists, False otherwise
    """
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        result = bind.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.table_constraints
            WHERE table_name = :table_name
            AND constraint_name = :constraint_name
        """), {"table_name": table_name, "constraint_name": constraint_name})
        return result.scalar() > 0
    except Exception:
        return False


def foreign_key_exists(table_name, fk_name):
    """Check if a foreign key constraint exists.

    Args:
        table_name (str): Name of the table
        fk_name (str): Name of the foreign key constraint

    Returns:
        bool: True if foreign key exists, False otherwise
    """
    if not table_exists(table_name):
        return False
    try:
        bind = op.get_bind()
        result = bind.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.table_constraints tc
            WHERE tc.table_name = :table_name
            AND tc.constraint_name = :fk_name
            AND tc.constraint_type = 'FOREIGN KEY'
        """), {"table_name": table_name, "fk_name": fk_name})
        return result.scalar() > 0
    except Exception:
        return False


def safe_add_column(table_name, column_def, verbose=True):
    """Safely add a column only if it doesn't exist.

    Args:
        table_name (str): Name of the table
        column_def: SQLAlchemy Column definition
        verbose (bool): Whether to print status messages

    Returns:
        bool: True if column was added, False if it already existed
    """
    if not table_exists(table_name):
        if verbose:
            print(f"   ⚠️  {table_name} table does not exist - skipping column add")
        return False

    column_name = column_def.name
    if column_exists(table_name, column_name):
        if verbose:
            print(f"   ✅ {column_name} column already exists - skipping")
        return False

    try:
        # Use batch operations for better transaction safety
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(column_def)
        if verbose:
            print(f"   ✅ {column_name} column added successfully")
        return True
    except Exception as e:
        if verbose:
            print(f"   ❌ Failed to add {column_name} column: {e}")
        # CRITICAL: Re-raise the exception to prevent transaction corruption
        # PostgreSQL needs to know about the failure to handle it properly
        raise


def safe_drop_column(table_name, column_name, verbose=True):
    """Safely drop a column only if it exists.

    Args:
        table_name (str): Name of the table
        column_name (str): Name of the column to drop
        verbose (bool): Whether to print status messages

    Returns:
        bool: True if column was dropped, False if it didn't exist
    """
    if column_exists(table_name, column_name):
        try:
            op.drop_column(table_name, column_name)
            if verbose:
                print(f"✅ Dropped {column_name} from {table_name}")
            return True
        except Exception as e:
            if verbose:
                print(f"⚠️  Error dropping {column_name} from {table_name}: {e}")
            return False
    else:
        if verbose:
            print(f"Column {column_name} doesn't exist in {table_name}")
        return False


def safe_create_index(index_name, table_name, columns, unique=False, verbose=True):
    """Safely create an index only if it doesn't exist.

    Args:
        index_name (str): Name of the index
        table_name (str): Name of the table
        columns (list): List of column names
        unique (bool): Whether the index should be unique
        verbose (bool): Whether to print status messages

    Returns:
        bool: True if index was created, False if it already existed
    """
    if not index_exists(table_name, index_name):
        try:
            op.create_index(index_name, table_name, columns, unique=unique)
            if verbose:
                print(f"✅ Created index {index_name} on {table_name}")
            return True
        except Exception as e:
            if verbose:
                print(f"⚠️  Error creating index {index_name}: {e}")
            return False
    else:
        if verbose:
            print(f"Index {index_name} already exists")
        return False


def safe_drop_index(index_name, table_name=None, verbose=True):
    """Safely drop an index only if it exists.

    Args:
        index_name (str): Name of the index
        table_name (str, optional): Name of the table (for checking)
        verbose (bool): Whether to print status messages

    Returns:
        bool: True if index was dropped, False if it didn't exist
    """
    if table_name and index_exists(table_name, index_name):
        try:
            op.drop_index(index_name, table_name=table_name)
            if verbose:
                print(f"✅ Dropped index {index_name}")
            return True
        except Exception as e:
            if verbose:
                print(f"⚠️  Error dropping index {index_name}: {e}")
            return False
    else:
        try:
            op.drop_index(index_name)
            if verbose:
                print(f"✅ Dropped index {index_name}")
            return True
        except Exception as e:
            if verbose:
                print(f"Index {index_name} doesn't exist or error: {e}")
            return False