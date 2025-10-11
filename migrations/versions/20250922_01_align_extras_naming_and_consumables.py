"""
Align naming for extras and ensure consumable tables and indexes exist

Revision ID: 20250922_01_align_extras
Revises: d953779b55a3
Create Date: 2025-09-22 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# Import the PostgreSQL helpers
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from postgres_helpers import table_exists, index_exists, column_exists, safe_create_index


revision = '20250922_01_align_extras'
down_revision = 'd953779b55a3'
branch_labels = None
depends_on = None


def upgrade():
    """Align naming for consumable tables and add missing indexes"""

    # Define indexes that should exist (only if the column exists)
    indexes_to_create = [
        ('batch_consumable', 'ix_batch_consumable_batch_id', 'batch_id'),
        ('batch_consumable', 'ix_batch_consumable_inventory_item_id', 'inventory_item_id'),
        ('batch_consumable', 'ix_batch_consumable_organization_id', 'organization_id'),
        ('extra_batch_consumable', 'ix_extra_batch_consumable_batch_id', 'batch_id'),
        ('extra_batch_consumable', 'ix_extra_batch_consumable_inventory_item_id', 'inventory_item_id'),
        ('extra_batch_consumable', 'ix_extra_batch_consumable_organization_id', 'organization_id'),
    ]

    # Create missing indexes only if both table and column exist
    for table_name, index_name, column_name in indexes_to_create:
        if table_exists(table_name):
            if column_exists(table_name, column_name):
                safe_create_index(index_name, table_name, [column_name], verbose=True)
            else:
                print(f"   ⚠️  Column {column_name} does not exist in {table_name} - skipping index {index_name}")
        else:
            print(f"   ⚠️  Table {table_name} does not exist - skipping index {index_name}")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop indexes if they exist
    index_names = [
        'ix_batch_consumable_batch_id',
        'ix_batch_consumable_inventory_item_id',
        'ix_batch_consumable_organization_id',
        'ix_extra_batch_consumable_batch_id',
        'ix_extra_batch_consumable_inventory_item_id',
        'ix_extra_batch_consumable_organization_id',
    ]

    # Alembic's op.drop_index will no-op if the index doesn't exist on some backends; guard anyway
    for idx in index_names:
        try:
            op.drop_index(idx)
        except Exception:
            pass

    # Do not drop tables by default to avoid data loss. Uncomment if needed.
    # if _has_table(sa.inspect(bind), 'extra_batch_consumable'):
    #     op.drop_table('extra_batch_consumable')
    # if _has_table(sa.inspect(bind), 'batch_consumable'):
    #     op.drop_table('batch_consumable')