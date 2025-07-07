
"""clean_product_sku_history_fix

Revision ID: clean_product_sku_history_fix
Revises: 3478c1df1783
Create Date: 2025-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'clean_product_sku_history_fix'
down_revision = '3478c1df1783'
branch_labels = None
depends_on = None

def upgrade():
    # Clean up any leftover temporary tables first
    conn = op.get_bind()
    try:
        conn.execute(sa.text("DROP TABLE IF EXISTS _alembic_tmp_product_sku_history"))
        conn.commit()
    except:
        pass
    
    # Check if the column already exists before trying to add it
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('product_sku_history')]
    
    # Only proceed if we still have sku_id and don't have inventory_item_id
    if 'sku_id' in columns and 'inventory_item_id' not in columns:
        # Get existing foreign key constraints and indexes
        existing_fks = inspector.get_foreign_keys('product_sku_history')
        existing_indexes = inspector.get_indexes('product_sku_history')
        
        # First, add the new column without constraints
        with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
            batch_op.add_column(sa.Column('inventory_item_id', sa.Integer(), nullable=True))
        
        # Update data - map sku_id values to inventory_item_id
        op.execute("""
            UPDATE product_sku_history 
            SET inventory_item_id = sku_id
            WHERE sku_id IS NOT NULL
        """)
        
        # Now make changes with proper constraint handling
        with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
            # Make inventory_item_id NOT NULL
            batch_op.alter_column('inventory_item_id', nullable=False)
            
            # Drop old indexes that reference sku_id - check if they exist first
            for idx in existing_indexes:
                if idx['name'] in ['idx_sku_remaining', 'idx_sku_timestamp']:
                    try:
                        batch_op.drop_index(idx['name'])
                    except:
                        pass
            
            # Create new indexes - but don't create if they already exist
            try:
                batch_op.create_index('idx_inventory_item_remaining', ['inventory_item_id', 'remaining_quantity'], unique=False)
            except:
                pass
            try:
                batch_op.create_index('idx_inventory_item_timestamp', ['inventory_item_id', 'timestamp'], unique=False)
            except:
                pass
            
            # Drop old foreign keys that reference sku_id
            for fk in existing_fks:
                if 'sku_id' in fk['constrained_columns'] and fk.get('name'):
                    try:
                        batch_op.drop_constraint(fk['name'], type_='foreignkey')
                    except:
                        pass
            
            # Drop the old sku_id column
            try:
                batch_op.drop_column('sku_id')
            except:
                pass
        
        # Finally, add the new foreign key constraint
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

def downgrade():
    # Reverse the changes
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        # Add back sku_id column
        batch_op.add_column(sa.Column('sku_id', sa.Integer(), nullable=True))
        
        # Copy data back
        op.execute("""
            UPDATE product_sku_history 
            SET sku_id = inventory_item_id
            WHERE inventory_item_id IS NOT NULL
        """)
        
        # Make sku_id NOT NULL
        batch_op.alter_column('sku_id', nullable=False)
        
        # Drop new indexes
        try:
            batch_op.drop_index('idx_inventory_item_remaining')
        except:
            pass
        try:
            batch_op.drop_index('idx_inventory_item_timestamp')
        except:
            pass
        
        # Create old indexes
        try:
            batch_op.create_index('idx_sku_remaining', ['sku_id', 'remaining_quantity'], unique=False)
        except:
            pass
        try:
            batch_op.create_index('idx_sku_timestamp', ['sku_id', 'timestamp'], unique=False)
        except:
            pass
        
        # Drop foreign key and column
        try:
            batch_op.drop_constraint('fk_product_sku_history_inventory_item', type_='foreignkey')
        except:
            pass
        batch_op.drop_column('inventory_item_id')
        
        # Recreate old foreign key
        try:
            batch_op.create_foreign_key('product_sku_history_ibfk_1', 'product_sku', ['sku_id'], ['inventory_item_id'])
        except:
            pass
