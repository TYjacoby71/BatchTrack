"""
Set ON DELETE SET NULL for inventory_item.global_item_id

Revision ID: 20250904_03
Revises: 20250904_02
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa

revision = '20250904_03'
down_revision = '20250904_02'
branch_labels = None
depends_on = None


def upgrade():
    # Drop and recreate FK with ON DELETE SET NULL
    try:
        op.drop_constraint('fk_inventory_item_global_item', 'inventory_item', type_='foreignkey')
    except Exception:
        pass
    op.create_foreign_key(
        'fk_inventory_item_global_item',
        'inventory_item', 'global_item',
        ['global_item_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    try:
        op.drop_constraint('fk_inventory_item_global_item', 'inventory_item', type_='foreignkey')
    except Exception:
        pass
    op.create_foreign_key(
        'fk_inventory_item_global_item',
        'inventory_item', 'global_item',
        ['global_item_id'], ['id']
    )

