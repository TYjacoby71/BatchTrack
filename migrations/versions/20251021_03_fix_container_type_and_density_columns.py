"""
Add missing columns for production: inventory_item.density and (container_type), global_item.container_type

Revision ID: 20251021_03
Revises: 20251021_02
Create Date: 2025-10-21 18:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = '20251021_03'
down_revision = '20251021_02'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(table: str, column: str) -> bool:
    if not table_exists(table):
        return False
    try:
        bind = op.get_bind()
        inspector = inspect(bind)
        cols = [c['name'] for c in inspector.get_columns(table)]
        return column in cols
    except Exception:
        return False


def safe_add_column(table: str, column: sa.Column) -> bool:
    if not table_exists(table):
        print(f"   ⚠️  Table {table} does not exist - skipping {column.name}")
        return False
    if column_exists(table, column.name):
        print(f"   ✅ {table}.{column.name} already exists")
        return False
    try:
        # Use batch mode for portability (SQLite, Postgres)
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(column)
        print(f"   ✅ Added {table}.{column.name}")
        return True
    except Exception as e:
        print(f"   ⚠️  Could not add column {table}.{column.name}: {e}")
        return False


def upgrade() -> None:
    print("=== Fix missing inventory density and container type columns ===")

    # 1) inventory_item.density (used by conversion/reference features)
    if table_exists('inventory_item'):
        safe_add_column('inventory_item', sa.Column('density', sa.Float(), nullable=True))

    # 2) global_item.container_type (used throughout curated globals and seeders)
    if table_exists('global_item'):
        safe_add_column('global_item', sa.Column('container_type', sa.String(length=64), nullable=True))

    # 3) inventory_item.container_type to align with application usage
    if table_exists('inventory_item'):
        added = safe_add_column('inventory_item', sa.Column('container_type', sa.String(length=64), nullable=True))

        # Backfill from container_shape if present and container_type is NULL
        try:
            if column_exists('inventory_item', 'container_type') and column_exists('inventory_item', 'container_shape'):
                bind = op.get_bind()
                result = bind.execute(text(
                    """
                    UPDATE inventory_item
                    SET container_type = container_shape
                    WHERE container_type IS NULL AND container_shape IS NOT NULL
                    """
                ))
                # result.rowcount may be None on some dialects; this is informational
                try:
                    print(f"   ✅ Backfilled inventory_item.container_type from container_shape (rows: {getattr(result, 'rowcount', 'n/a')})")
                except Exception:
                    print("   ✅ Backfilled inventory_item.container_type from container_shape")
        except Exception as e:
            print(f"   ⚠️  Backfill from container_shape skipped due to error: {e}")

    print("✅ Column fixes complete")


def downgrade() -> None:
    # Conservative: do not drop columns in production to avoid data loss
    print("=== Downgrade no-op: preserving added columns ===")
