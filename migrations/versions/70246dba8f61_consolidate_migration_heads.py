
"""consolidate_migration_heads

Revision ID: 70246dba8f61
Revises: 1e08f080c0a6
Create Date: 2025-05-30 19:50:36.538425

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '70246dba8f61'
down_revision = '1e08f080c0a6'
branch_labels = None
depends_on = None

def upgrade():
    # Ensure all required columns exist
    try:
        # Check if unit column exists in inventory_history
        connection = op.get_bind()
        result = connection.execute(sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'inventory_history' 
            AND column_name = 'unit'
        """))
        
        if not result.fetchone():
            # Add unit column if it doesn't exist
            op.add_column('inventory_history', sa.Column('unit', sa.String(32), nullable=True))
            
            # Backfill existing records
            connection.execute(sa.text("""
                UPDATE inventory_history 
                SET unit = (
                    SELECT inventory_item.unit 
                    FROM inventory_item 
                    WHERE inventory_item.id = inventory_history.inventory_item_id
                )
                WHERE unit IS NULL
            """))
            
            # Make column non-nullable
            op.alter_column('inventory_history', 'unit', nullable=False)
            
    except Exception as e:
        print(f"Unit column handling: {e}")
    
    # Ensure ExtraBatchContainer has required fields
    try:
        # Check for quantity_used column
        result = connection.execute(sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'extra_batch_container' 
            AND column_name = 'quantity_used'
        """))
        
        if not result.fetchone():
            op.add_column('extra_batch_container', sa.Column('quantity_used', sa.Integer(), nullable=False, server_default='0'))
            
        # Check for cost_each column  
        result = connection.execute(sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'extra_batch_container' 
            AND column_name = 'cost_each'
        """))
        
        if not result.fetchone():
            op.add_column('extra_batch_container', sa.Column('cost_each', sa.Float(), nullable=True))
            
    except Exception as e:
        print(f"ExtraBatchContainer handling: {e}")
    
    # Ensure inventory_item has is_archived column
    try:
        result = connection.execute(sa.text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'inventory_item' 
            AND column_name = 'is_archived'
        """))
        
        if not result.fetchone():
            op.add_column('inventory_item', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default='false'))
            
    except Exception as e:
        print(f"InventoryItem is_archived handling: {e}")

def downgrade():
    # Remove added columns in reverse order
    try:
        op.drop_column('inventory_item', 'is_archived')
    except:
        pass
        
    try:
        op.drop_column('extra_batch_container', 'cost_each')
        op.drop_column('extra_batch_container', 'quantity_used')
    except:
        pass
        
    try:
        op.drop_column('inventory_history', 'unit')
    except:
        pass
