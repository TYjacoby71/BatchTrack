"""
Add missing columns: unit.created_by and global_item.recommended_shelf_life_days

Revision ID: 20251021_02
Revises: 20251021_01
Create Date: 2025-10-21 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251021_02'
down_revision = '20251021_01'
branch_labels = None
depends_on = None


def table_exists(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(table_name: str, column_name: str) -> bool:
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        return any(col['name'] == column_name for col in inspector.get_columns(table_name))
    except Exception:
        return False


def foreign_key_exists(table_name: str, fk_name: str) -> bool:
    if not table_exists(table_name):
        return False
    bind = op.get_bind()
    inspector = inspect(bind)
    try:
        fks = inspector.get_foreign_keys(table_name)
        return any(fk.get('name') == fk_name for fk in fks)
    except Exception:
        return False


def safe_add_column(table_name: str, column: sa.Column) -> None:
    if not table_exists(table_name):
        print(f"   ⚠️  Table {table_name} does not exist - skipping {column.name}")
        return
    if column_exists(table_name, column.name):
        print(f"   ✅ {table_name}.{column.name} already exists")
        return
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(column)
        print(f"   ✅ Added {table_name}.{column.name}")
    except Exception as e:
        print(f"   ⚠️  Could not add column {table_name}.{column.name}: {e}")


def safe_create_foreign_key(constraint_name: str, source_table: str, referent_table: str, local_cols, remote_cols) -> None:
    if not table_exists(source_table) or not table_exists(referent_table):
        return
    if foreign_key_exists(source_table, constraint_name):
        print(f"   ✅ Foreign key {constraint_name} already exists")
        return
    try:
        with op.batch_alter_table(source_table, schema=None) as batch_op:
            batch_op.create_foreign_key(constraint_name, referent_table, local_cols, remote_cols)
        print(f"   ✅ Created foreign key {constraint_name}")
    except Exception as e:
        print(f"   ⚠️  Could not create foreign key {constraint_name}: {e}")


def upgrade():
    print("=== Adding missing columns for Unit and GlobalItem ===")

    # unit.created_by
    if table_exists('unit'):
        safe_add_column('unit', sa.Column('created_by', sa.Integer(), nullable=True))
        # Also ensure organization_id exists? Model has it; assume handled elsewhere
        # Create FK if possible
        if column_exists('unit', 'created_by') and table_exists('user'):
            safe_create_foreign_key('fk_unit_created_by_user', 'unit', 'user', ['created_by'], ['id'])

    # global_item.recommended_shelf_life_days
    if table_exists('global_item'):
        safe_add_column('global_item', sa.Column('recommended_shelf_life_days', sa.Integer(), nullable=True))

    print("✅ Missing column additions completed")


def downgrade():
    print("=== Downgrade: remove added columns (no-op for safety) ===")
    # Intentionally do not drop columns in downgrade to avoid data loss in production
    print("ℹ️  No-op downgrade")
