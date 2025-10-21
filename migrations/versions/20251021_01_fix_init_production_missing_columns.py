"""
Add missing columns for init-production compatibility (developer_role, unit, ingredient_category)

Revision ID: 20251021_01
Revises: 20251020_2
Create Date: 2025-10-21 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20251021_01'
down_revision = '20251020_2'
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


def safe_add_column(table_name: str, col: sa.Column) -> None:
    if not table_exists(table_name):
        print(f"   ⚠️  Table {table_name} does not exist - skipping {col.name}")
        return
    if column_exists(table_name, col.name):
        print(f"   ✅ {table_name}.{col.name} already exists")
        return
    try:
        # Use batch_alter_table for SQLite compatibility
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.add_column(col)
        print(f"   ✅ Added {table_name}.{col.name}")
    except Exception as e:
        print(f"   ⚠️  Could not add column {table_name}.{col.name}: {e}")


def upgrade():
    print("=== Fixing missing columns for init-production ===")

    # developer_role.category
    if table_exists('developer_role'):
        safe_add_column('developer_role', sa.Column('category', sa.String(length=32), nullable=True))
        # Ensure is_active and created_at exist (some seeds query them)
        safe_add_column('developer_role', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')))
        safe_add_column('developer_role', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))

    # unit.is_custom, unit.is_mapped
    if table_exists('unit'):
        safe_add_column('unit', sa.Column('is_custom', sa.Boolean(), nullable=True, server_default=sa.text('false')))
        safe_add_column('unit', sa.Column('is_mapped', sa.Boolean(), nullable=True, server_default=sa.text('false')))

    # ingredient_category standard fields used in models/seeders
    if table_exists('ingredient_category'):
        safe_add_column('ingredient_category', sa.Column('description', sa.Text(), nullable=True))
        safe_add_column('ingredient_category', sa.Column('color', sa.String(length=7), nullable=True))
        safe_add_column('ingredient_category', sa.Column('default_density', sa.Float(), nullable=True))
        safe_add_column('ingredient_category', sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('true')))
        safe_add_column('ingredient_category', sa.Column('created_by', sa.Integer(), nullable=True))
        # created_at/updated_at are added in other migrations, but keep safe
        safe_add_column('ingredient_category', sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))
        safe_add_column('ingredient_category', sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('CURRENT_TIMESTAMP')))
        # visibility controls
        for flag in (
            'show_saponification_value', 'show_iodine_value', 'show_melting_point',
            'show_flash_point', 'show_ph_value', 'show_moisture_content',
            'show_shelf_life_months', 'show_comedogenic_rating'
        ):
            safe_add_column('ingredient_category', sa.Column(flag, sa.Boolean(), nullable=True, server_default=sa.text('false')))
        # global category toggle
        safe_add_column('ingredient_category', sa.Column('is_global_category', sa.Boolean(), nullable=True, server_default=sa.text('false')))

    print("✅ Missing columns fix complete")


def downgrade():
    print("=== Downgrading missing column fixes ===")
    # Intentionally conservative: do not drop columns to avoid data loss in production.
    print("ℹ️  No-op downgrade (columns preserved)")
