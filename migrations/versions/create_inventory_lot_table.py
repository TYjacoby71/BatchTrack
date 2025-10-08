"""Create inventory_lot table for proper FIFO tracking

Revision ID: create_inventory_lot
Revises: fix_product_sku_id_autoincrement
Create Date: 2025-08-21 04:57:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'create_inventory_lot'
down_revision = 'fix_product_sku_id_autoincrement'
branch_labels = None
depends_on = None


def upgrade():
    """Create inventory_lot table for proper FIFO tracking"""
    print("=== Creating inventory_lot table ===")
    
    # Check if table already exists
    from alembic import op
    import sqlalchemy as sa
    from sqlalchemy import inspect

    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'inventory_lot' in existing_tables:
        print("   ✅ inventory_lot table already exists - skipping creation")
        
        # Still create indexes if they don't exist
        existing_indexes = []
        try:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('inventory_lot')]
        except Exception:
            existing_indexes = []

        indexes_to_create = [
            ('idx_inventory_lot_item_remaining', ['inventory_item_id', 'remaining_quantity']),
            ('idx_inventory_lot_received_date', ['received_date']),
            ('idx_inventory_lot_expiration', ['expiration_date']),
            ('idx_inventory_lot_organization', ['organization_id'])
        ]

        for idx_name, columns in indexes_to_create:
            if idx_name not in existing_indexes:
                try:
                    op.create_index(idx_name, 'inventory_lot', columns)
                    print(f"   ✅ Created index: {idx_name}")
                except Exception as e:
                    print(f"   ⚠️  Could not create index {idx_name}: {e}")
            else:
                print(f"   ⚠️  Index {idx_name} already exists - skipping")
        
        print("✅ inventory_lot migration completed (table existed)")
        return

    print("   Creating inventory_lot table...")
    op.create_table(
        'inventory_lot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_item_id', sa.Integer(), nullable=False),
        sa.Column('remaining_quantity', sa.Float(), nullable=False, default=0.0),
        sa.Column('original_quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(32), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False, default=0.0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('received_date', sa.DateTime(), nullable=False),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('shelf_life_days', sa.Integer(), nullable=True),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('fifo_code', sa.String(32), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['inventory_item_id'], ['inventory_item.id']),
        sa.ForeignKeyConstraint(['created_by'], ['user.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organization.id']),
        sa.UniqueConstraint('fifo_code'),
        sa.CheckConstraint('remaining_quantity >= 0', name='check_remaining_quantity_non_negative'),
        sa.CheckConstraint('original_quantity > 0', name='check_original_quantity_positive'),
        sa.CheckConstraint('remaining_quantity <= original_quantity', name='check_remaining_not_exceeds_original'),
    )

    # Create indexes for performance
    print("   Creating indexes...")
    op.create_index('idx_inventory_lot_item_remaining', 'inventory_lot', ['inventory_item_id', 'remaining_quantity'])
    op.create_index('idx_inventory_lot_received_date', 'inventory_lot', ['received_date'])
    op.create_index('idx_inventory_lot_expiration', 'inventory_lot', ['expiration_date'])
    op.create_index('idx_inventory_lot_organization', 'inventory_lot', ['organization_id'])
    
    print("✅ inventory_lot table and indexes created successfully")


def downgrade():
    # Drop indexes first
    op.drop_index('idx_inventory_lot_organization')
    op.drop_index('idx_inventory_lot_expiration')
    op.drop_index('idx_inventory_lot_received_date')
    op.drop_index('idx_inventory_lot_item_remaining')

    # Drop table
    op.drop_table('inventory_lot')