"""
Global items table, link to inventory_item, and performance indexes

Revision ID: 20250904_01
Revises: add_reference_guide_integration
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250904_01'
down_revision = 'add_reference_guide_integration'
branch_labels = None
depends_on = None


def upgrade():
    # 1) Create global_item table
    op.create_table(
        'global_item',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('item_type', sa.String(length=32), nullable=False),
        sa.Column('default_unit', sa.String(length=32), nullable=True),
        sa.Column('density', sa.Float(), nullable=True),
        sa.Column('capacity', sa.Float(), nullable=True),
        sa.Column('capacity_unit', sa.String(length=32), nullable=True),
        sa.Column('suggested_inventory_category_id', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.UniqueConstraint('name', 'item_type', name='_global_item_name_type_uc')
    )
    op.create_index('ix_global_item_name', 'global_item', ['name'])
    op.create_index('ix_global_item_item_type', 'global_item', ['item_type'])

    # 2) Add global_item_id to inventory_item
    op.add_column('inventory_item', sa.Column('global_item_id', sa.Integer(), nullable=True))
    op.create_index('ix_inventory_item_global_item_id', 'inventory_item', ['global_item_id'])
    op.create_foreign_key('fk_inventory_item_global_item', 'inventory_item', 'global_item', ['global_item_id'], ['id'])

    # 3) Adjust uniqueness on inventory_item.name to be per-organization
    # Drop prior unique constraint or unique index on name if it exists
    try:
        op.drop_constraint('inventory_item_name_key', 'inventory_item', type_='unique')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_name', table_name='inventory_item')
    except Exception:
        pass

    # Ensure name is indexed (non-unique) and add composite unique
    try:
        op.create_index('ix_inventory_item_name', 'inventory_item', ['name'])
    except Exception:
        # If index exists, ignore
        pass
    try:
        op.create_unique_constraint('_org_name_uc', 'inventory_item', ['organization_id', 'name'])
    except Exception:
        # If constraint exists, ignore
        pass

    # 4) Performance indexes on inventory_item
    # Some may exist; wrap in try/except to be idempotent for partial deployments
    for idx_name, cols in [
        ('ix_inventory_item_organization_id', ['organization_id']),
        ('ix_inventory_item_type', ['type']),
        ('ix_inventory_item_is_archived', ['is_archived'])
    ]:
        try:
            op.create_index(idx_name, 'inventory_item', cols)
        except Exception:
            pass

    # 5) Index on user.organization_id for multi-tenant performance
    try:
        op.create_index('ix_user_organization_id', 'user', ['organization_id'])
    except Exception:
        pass


def downgrade():
    # Reverse user index
    try:
        op.drop_index('ix_user_organization_id', table_name='user')
    except Exception:
        pass

    # Reverse inventory_item indexes/constraints
    try:
        op.drop_constraint('_org_name_uc', 'inventory_item', type_='unique')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_is_archived', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_type', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_organization_id', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_global_item_id', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_inventory_item_name', table_name='inventory_item')
    except Exception:
        pass
    try:
        op.drop_constraint('fk_inventory_item_global_item', 'inventory_item', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_column('inventory_item', 'global_item_id')
    except Exception:
        pass

    # Drop global_item table and indexes
    try:
        op.drop_index('ix_global_item_item_type', table_name='global_item')
    except Exception:
        pass
    try:
        op.drop_index('ix_global_item_name', table_name='global_item')
    except Exception:
        pass
    try:
        op.drop_table('global_item')
    except Exception:
        pass
