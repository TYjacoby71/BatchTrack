
"""
PostgreSQL and SQLite migration helper utilities
"""
from sqlalchemy import text, inspect
from alembic import op
import logging

logger = logging.getLogger('alembic.helpers')

def is_sqlite():
    """Check if we're running on SQLite"""
    connection = op.get_bind()
    return 'sqlite' in str(connection.engine.url)

def is_postgresql():
    """Check if we're running on PostgreSQL"""
    connection = op.get_bind()
    return 'postgresql' in str(connection.engine.url)

def clean_sqlite_temp_tables():
    """Clean up any leftover temporary tables from failed SQLite migrations"""
    if not is_sqlite():
        return
        
    connection = op.get_bind()
    try:
        # Get list of all temporary tables
        result = connection.execute(text("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE '_alembic_tmp_%'
        """))
        temp_tables = [row[0] for row in result.fetchall()]
        
        if temp_tables:
            logger.info(f"🧹 Cleaning up {len(temp_tables)} temporary tables")
            for table_name in temp_tables:
                try:
                    connection.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                    logger.info(f"   ✅ Cleaned: {table_name}")
                except Exception as e:
                    logger.warning(f"   ⚠️  Failed to clean {table_name}: {e}")
            connection.commit()
    except Exception as e:
        logger.warning(f"⚠️  Could not clean temporary tables: {e}")

def safe_batch_alter_table(table_name, **kwargs):
    """Safely alter a table with automatic temp table cleanup for SQLite"""
    clean_sqlite_temp_tables()  # Clean before operation
    
    try:
        with op.batch_alter_table(table_name, **kwargs) as batch_op:
            yield batch_op
    except Exception as e:
        # If batch operation fails, clean up and re-raise
        if is_sqlite():
            logger.warning(f"Batch operation failed, cleaning temporary tables: {e}")
            clean_sqlite_temp_tables()
        raise

def safe_drop_column(table_name, column_name):
    """Safely drop a column with automatic cleanup"""
    inspector = inspect(op.get_bind())
    
    # Check if column exists
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    if column_name not in columns:
        logger.info(f"   ℹ️  Column {column_name} doesn't exist in {table_name}, skipping")
        return
    
    clean_sqlite_temp_tables()  # Clean before operation
    
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column(column_name)
        logger.info(f"   ✅ Dropped {column_name} from {table_name}")
    except Exception as e:
        logger.warning(f"   ⚠️  Failed to drop {column_name} from {table_name}: {e}")
        if is_sqlite():
            clean_sqlite_temp_tables()
        raise

def safe_add_column(table_name, column_name, column_type, **kwargs):
    """Safely add a column with automatic cleanup"""
    inspector = inspect(op.get_bind())
    
    # Check if column already exists
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    if column_name in columns:
        logger.info(f"   ℹ️  Column {column_name} already exists in {table_name}, skipping")
        return
    
    clean_sqlite_temp_tables()  # Clean before operation
    
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(op.Column(column_name, column_type, **kwargs))
        logger.info(f"   ✅ Added {column_name} to {table_name}")
    except Exception as e:
        logger.warning(f"   ⚠️  Failed to add {column_name} to {table_name}: {e}")
        if is_sqlite():
            clean_sqlite_temp_tables()
        raise

def table_exists(table_name):
    """Check if table exists"""
    inspector = inspect(op.get_bind())
    return table_name in inspector.get_table_names()

def column_exists(table_name, column_name):
    """Check if column exists in table"""
    if not table_exists(table_name):
        return False
    inspector = inspect(op.get_bind())
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

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
    # First check if table exists
    if not table_exists(table_name):
        if verbose:
            print(f"   ⚠️  Table {table_name} doesn't exist - skipping index {index_name}")
        return False
        
    # Check if all columns exist
    for col in columns:
        if not column_exists(table_name, col):
            if verbose:
                print(f"   ⚠️  Column {col} doesn't exist in {table_name} - skipping index {index_name}")
            return False
    
    # Check if index already exists
    if index_exists(table_name, index_name):
        if verbose:
            print(f"   ✅ Index {index_name} already exists")
        return False
        
    # Try to create the index
    try:
        op.create_index(index_name, table_name, columns, unique=unique)
        if verbose:
            print(f"   ✅ Created index {index_name} on {table_name}")
        return True
    except Exception as e:
        if verbose:
            print(f"   ⚠️  Error creating index {index_name}: {e}")
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