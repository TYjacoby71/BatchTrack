
"""Consolidate to single ProductSKU table

Revision ID: consolidate_to_single_sku_table
Revises: consolidate_product_system
Create Date: 2025-06-25 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers
revision = 'consolidate_to_single_sku_table'
down_revision = 'consolidate_product_system'
branch_labels = None
depends_on = None

def upgrade():
    # Add new fields to product_sku table to make it the single source
    with op.batch_alter_table('product_sku') as batch_op:
        # Product-level fields
        batch_op.add_column(sa.Column('product_name', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('product_base_unit', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('variant_description', sa.Text, nullable=True))
        batch_op.add_column(sa.Column('is_product_active', sa.Boolean, default=True))
        
        # Inventory fields
        batch_op.add_column(sa.Column('current_quantity', sa.Float, default=0.0))
        batch_op.add_column(sa.Column('unit_cost', sa.Float, nullable=True))
        batch_op.add_column(sa.Column('batch_id', sa.Integer, nullable=True))
        batch_op.add_column(sa.Column('container_id', sa.Integer, nullable=True))
        
        # Expiration fields
        batch_op.add_column(sa.Column('is_perishable', sa.Boolean, default=False))
        batch_op.add_column(sa.Column('shelf_life_days', sa.Integer, nullable=True))
        batch_op.add_column(sa.Column('expiration_date', sa.DateTime, nullable=True))
        
        # Metadata
        batch_op.add_column(sa.Column('last_updated', sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column('notes', sa.Text, nullable=True))
    
    # Migrate data from existing tables to product_sku
    connection = op.get_bind()
    
    # First, populate product_name and product_base_unit from product table
    connection.execute(text("""
        UPDATE product_sku 
        SET product_name = (
            SELECT p.name FROM product p WHERE p.id = product_sku.product_id
        ),
        product_base_unit = (
            SELECT p.product_base_unit FROM product p WHERE p.id = product_sku.product_id
        ),
        is_product_active = (
            SELECT p.is_active FROM product p WHERE p.id = product_sku.product_id
        )
    """))
    
    # Migrate variant descriptions
    connection.execute(text("""
        UPDATE product_sku 
        SET variant_description = (
            SELECT pv.description FROM product_variation pv WHERE pv.id = product_sku.variant_id
        )
    """))
    
    # Aggregate inventory quantities by SKU
    connection.execute(text("""
        UPDATE product_sku 
        SET current_quantity = COALESCE((
            SELECT SUM(pi.quantity) 
            FROM product_inventory pi 
            WHERE pi.sku_id = product_sku.id
        ), 0)
    """))
    
    # Set last_updated to created_at initially
    connection.execute(text("""
        UPDATE product_sku 
        SET last_updated = created_at
    """))
    
    # Make product_name and product_base_unit required
    with op.batch_alter_table('product_sku') as batch_op:
        batch_op.alter_column('product_name', nullable=False)
        batch_op.alter_column('product_base_unit', nullable=False)
    
    # Create the simplified history table
    op.create_table('product_sku_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sku_id', sa.Integer(), sa.ForeignKey('product_sku.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('change_type', sa.String(32), nullable=False),
        sa.Column('quantity_change', sa.Float(), nullable=False),
        sa.Column('old_quantity', sa.Float(), nullable=False),
        sa.Column('new_quantity', sa.Float(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('sale_price', sa.Float(), nullable=True),
        sa.Column('customer', sa.String(128), nullable=True),
        sa.Column('batch_id', sa.Integer(), sa.ForeignKey('batch.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('user.id'), nullable=True)
    )
    
    # Create indexes for performance
    op.create_index('idx_product_name', 'product_sku', ['product_name'])
    op.create_index('idx_variant_name', 'product_sku', ['variant_name'])
    op.create_index('idx_active_skus', 'product_sku', ['is_active', 'is_product_active'])
    
    # Drop the old tables
    op.drop_table('product_inventory_history')
    op.drop_table('product_inventory')
    op.drop_table('product_event')
    op.drop_table('product_variation')
    op.drop_table('product')

def downgrade():
    # This would be complex to implement - recommend backup before migration
    raise NotImplementedError("Downgrade not supported for this consolidation migration")
