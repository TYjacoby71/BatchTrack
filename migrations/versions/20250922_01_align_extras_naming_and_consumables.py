"""
Align naming for extras and ensure consumable tables and indexes exist

Revision ID: 20250922_01_align_extras
Revises: d953779b55a3
Create Date: 2025-09-22

This migration is intentionally conservative and idempotent:
- Verifies presence of batch_consumable and extra_batch_consumable tables, creating them if missing
- Adds helpful indexes on (batch_id), (inventory_item_id), and (organization_id) if missing

Note: No destructive renames are performed here. Update as needed.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250922_01_align_extras'
down_revision = 'd953779b55a3'
branch_labels = None
depends_on = None


def _has_table(inspector, table_name: str) -> bool:
    try:
        return table_name in inspector.get_table_names()  # type: ignore
    except Exception:
        return False


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    try:
        indexes = inspector.get_indexes(table_name)  # type: ignore
        return any(idx.get('name') == index_name for idx in indexes)
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Ensure batch_consumable table exists (if prior migration didn't run)
    if not _has_table(inspector, 'batch_consumable'):
        op.create_table(
            'batch_consumable',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batch.id'), nullable=False),
            sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_item.id'), nullable=False),
            sa.Column('quantity_used', sa.Float(), nullable=False),
            sa.Column('unit', sa.String(length=32), nullable=False),
            sa.Column('cost_per_unit', sa.Float(), nullable=True),
            sa.Column('total_cost', sa.Float(), nullable=True),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True),
        )

    # Ensure extra_batch_consumable table exists
    if not _has_table(inspector, 'extra_batch_consumable'):
        op.create_table(
            'extra_batch_consumable',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batch.id'), nullable=False),
            sa.Column('inventory_item_id', sa.Integer(), sa.ForeignKey('inventory_item.id'), nullable=False),
            sa.Column('quantity_used', sa.Float(), nullable=False),
            sa.Column('unit', sa.String(length=32), nullable=False),
            sa.Column('cost_per_unit', sa.Float(), nullable=True),
            sa.Column('total_cost', sa.Float(), nullable=True),
            sa.Column('reason', sa.String(length=20), nullable=False, server_default='extra_use'),
            sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organization.id'), nullable=True),
        )

    # Refresh inspector after potential table creation
    inspector = sa.inspect(bind)

    # Add helpful indexes if missing
    idx_defs = {
        'batch_consumable': [
            ('ix_batch_consumable_batch_id', ['batch_id']),
            ('ix_batch_consumable_inventory_item_id', ['inventory_item_id']),
            ('ix_batch_consumable_organization_id', ['organization_id']),
        ],
        'extra_batch_consumable': [
            ('ix_extra_batch_consumable_batch_id', ['batch_id']),
            ('ix_extra_batch_consumable_inventory_item_id', ['inventory_item_id']),
            ('ix_extra_batch_consumable_organization_id', ['organization_id']),
        ],
    }

    for table, index_list in idx_defs.items():
        if _has_table(inspector, table):
            for index_name, cols in index_list:
                if not _has_index(inspector, table, index_name):
                    op.create_index(index_name, table, cols)


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

