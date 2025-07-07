
"""Merge schema fix branches

Revision ID: e9cc6a2cdcd9
Revises: clean_product_sku_history_fix, fix_product_sku_history_schema
Create Date: 2025-07-07 21:34:36.156000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e9cc6a2cdcd9'
down_revision = ('clean_product_sku_history_fix', 'fix_product_sku_history_schema')
branch_labels = None
depends_on = None

def upgrade():
    # Ensure the product_sku_history table has the correct schema
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('product_sku_history')]
    
    # If sku_id still exists, remove it and ensure inventory_item_id is proper
    if 'sku_id' in columns:
        with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
            # Drop the sku_id column
            batch_op.drop_column('sku_id')
    
    # Ensure inventory_item_id has proper foreign key
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        # Drop existing foreign key if it exists
        try:
            batch_op.drop_constraint('fk_product_sku_history_inventory_item_id', type_='foreignkey')
        except:
            pass
        
        # Add correct foreign key
        batch_op.create_foreign_key(
            'fk_product_sku_history_inventory_item_id',
            'inventory_item',
            ['inventory_item_id'],
            ['id']
        )

def downgrade():
    # Reverse the changes
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        # Add back sku_id column
        batch_op.add_column(sa.Column('sku_id', sa.Integer(), nullable=True))
        
        # Copy data back if needed
        op.execute("""
            UPDATE product_sku_history 
            SET sku_id = inventory_item_id
            WHERE inventory_item_id IS NOT NULL
        """)
        
        # Make sku_id NOT NULL
        batch_op.alter_column('sku_id', nullable=False)
        
        # Drop new foreign key
        try:
            batch_op.drop_constraint('fk_product_sku_history_inventory_item_id', type_='foreignkey')
        except:
            pass
        
        # Create old foreign key
        try:
            batch_op.create_foreign_key('product_sku_history_ibfk_1', 'product_sku', ['sku_id'], ['inventory_item_id'])
        except:
            pass
