
"""Merge all migration heads

Revision ID: ad231d0d88cc
Revises: clean_product_sku_history_fix, fix_product_sku_history_schema
Create Date: 2025-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ad231d0d88cc'
down_revision = ('clean_product_sku_history_fix', 'fix_product_sku_history_schema')
branch_labels = None
depends_on = None

def upgrade():
    # This is a merge migration that consolidates all pending schema changes
    # Check current state and apply any missing changes
    
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check product_sku_history table schema
    try:
        columns = [col['name'] for col in inspector.get_columns('product_sku_history')]
        
        # If we still have sku_id column and no inventory_item_id, apply the fix
        if 'sku_id' in columns and 'inventory_item_id' not in columns:
            print("Applying product_sku_history schema fix...")
            
            # Add inventory_item_id column
            with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
                batch_op.add_column(sa.Column('inventory_item_id', sa.Integer(), nullable=True))
            
            # Update data - map sku_id values to inventory_item_id
            # Since ProductSKU.inventory_item_id maps to the same values as the old sku_id
            op.execute("""
                UPDATE product_sku_history 
                SET inventory_item_id = sku_id
                WHERE sku_id IS NOT NULL
            """)
            
            # Make inventory_item_id NOT NULL and clean up
            with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
                # Make inventory_item_id NOT NULL
                batch_op.alter_column('inventory_item_id', nullable=False)
                
                # Drop old indexes
                try:
                    batch_op.drop_index('idx_sku_remaining')
                except:
                    pass
                try:
                    batch_op.drop_index('idx_sku_timestamp')
                except:
                    pass
                
                # Create new indexes
                try:
                    batch_op.create_index('idx_inventory_item_remaining', ['inventory_item_id', 'remaining_quantity'], unique=False)
                except:
                    pass
                try:
                    batch_op.create_index('idx_inventory_item_timestamp', ['inventory_item_id', 'timestamp'], unique=False)
                except:
                    pass
                
                # Drop the old sku_id column
                batch_op.drop_column('sku_id')
            
            # Add foreign key constraint
            with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
                try:
                    batch_op.create_foreign_key(
                        'fk_product_sku_history_inventory_item', 
                        'product_sku', 
                        ['inventory_item_id'], 
                        ['inventory_item_id']
                    )
                except:
                    pass
    
    except Exception as e:
        print(f"product_sku_history already updated or error occurred: {e}")
    
    # Ensure ProductSKU table has inventory_item_id as NOT NULL
    try:
        product_sku_columns = [col['name'] for col in inspector.get_columns('product_sku')]
        if 'inventory_item_id' in product_sku_columns:
            with op.batch_alter_table('product_sku', schema=None) as batch_op:
                batch_op.alter_column('inventory_item_id',
                       existing_type=sa.INTEGER(),
                       nullable=False)
    except Exception as e:
        print(f"ProductSKU inventory_item_id already configured: {e}")

def downgrade():
    # This is a merge migration, downgrade would be complex
    # Individual migrations handle their own downgrades
    pass
