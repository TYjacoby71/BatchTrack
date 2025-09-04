"""
Repair: ensure global_item exists with indexes and FK

Revision ID: 20250904_01a
Revises: 20250904_01
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250904_01a'
down_revision = '20250904_01'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import text

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1) Ensure global_item table exists
    if not inspector.has_table('global_item'):
        print("Repair: creating missing global_item table...")
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
        print("   ✅ global_item created")

    # Refresh inspector data
    inspector = sa.inspect(bind)

    # 2) Ensure indexes on global_item
    global_item_indexes = {idx['name'] for idx in inspector.get_indexes('global_item')}
    if 'ix_global_item_name' not in global_item_indexes:
        try:
            op.create_index('ix_global_item_name', 'global_item', ['name'])
            print("   ✅ Created index: ix_global_item_name")
        except Exception:
            pass
    if 'ix_global_item_item_type' not in global_item_indexes:
        try:
            op.create_index('ix_global_item_item_type', 'global_item', ['item_type'])
            print("   ✅ Created index: ix_global_item_item_type")
        except Exception:
            pass

    # 3) Ensure inventory_item column and index exist
    inventory_item_columns = {col['name'] for col in inspector.get_columns('inventory_item')}
    if 'global_item_id' not in inventory_item_columns:
        try:
            op.add_column('inventory_item', sa.Column('global_item_id', sa.Integer(), nullable=True))
            print("   ✅ Added column: inventory_item.global_item_id")
        except Exception:
            pass

    inv_indexes = {idx['name'] for idx in inspector.get_indexes('inventory_item')}
    if 'ix_inventory_item_global_item_id' not in inv_indexes:
        try:
            op.create_index('ix_inventory_item_global_item_id', 'inventory_item', ['global_item_id'])
            print("   ✅ Created index: ix_inventory_item_global_item_id")
        except Exception:
            pass

    # 4) Ensure FK exists
    fk_exists = False
    try:
        result = bind.execute(text(
            """
            SELECT 1
            FROM information_schema.table_constraints tc
            WHERE tc.constraint_name = 'fk_inventory_item_global_item'
              AND tc.table_name = 'inventory_item'
              AND tc.constraint_type = 'FOREIGN KEY'
            """
        ))
        fk_exists = result.first() is not None
    except Exception:
        fk_exists = False

    if not fk_exists:
        try:
            op.create_foreign_key(
                'fk_inventory_item_global_item',
                'inventory_item', 'global_item',
                ['global_item_id'], ['id']
            )
            print("   ✅ Created FK: fk_inventory_item_global_item")
        except Exception:
            pass


def downgrade():
    # No-op repair downgrade
    pass

