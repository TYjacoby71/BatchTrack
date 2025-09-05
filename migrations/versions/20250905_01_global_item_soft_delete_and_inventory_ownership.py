"""
Add soft-delete fields to global_item and ownership to inventory_item

Revision ID: 2025090501
Revises: 2025090404
Create Date: 2025-09-05
"""

from alembic import op
import sqlalchemy as sa

revision = '2025090501'
down_revision = '2025090404'
branch_labels = None
depends_on = None


def upgrade():
    # GlobalItem soft-delete columns
    try:
        op.add_column('global_item', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    except Exception:
        pass
    try:
        op.add_column('global_item', sa.Column('archived_at', sa.DateTime(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('global_item', sa.Column('archived_by', sa.Integer(), nullable=True))
    except Exception:
        pass
    try:
        op.create_index('ix_global_item_is_archived', 'global_item', ['is_archived'])
    except Exception:
        pass

    # InventoryItem ownership column
    try:
        op.add_column('inventory_item', sa.Column('ownership', sa.String(length=16), nullable=True))
    except Exception:
        pass
    try:
        op.create_index('ix_inventory_item_ownership', 'inventory_item', ['ownership'])
    except Exception:
        pass

    # Backfill ownership where possible
    try:
        op.execute("UPDATE inventory_item SET ownership = CASE WHEN global_item_id IS NOT NULL THEN 'global' ELSE 'org' END WHERE ownership IS NULL")
    except Exception:
        pass


def downgrade():
    # Drop indexes and columns
    try:
        op.drop_index('ix_inventory_item_ownership', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_column('inventory_item', 'ownership')
    except Exception:
        pass

    try:
        op.drop_index('ix_global_item_is_archived', table_name='global_item')
    except Exception:
        pass
    try:
        op.drop_column('global_item', 'archived_by')
    except Exception:
        pass
    try:
        op.drop_column('global_item', 'archived_at')
    except Exception:
        pass
    try:
        op.drop_column('global_item', 'is_archived')
    except Exception:
        pass

