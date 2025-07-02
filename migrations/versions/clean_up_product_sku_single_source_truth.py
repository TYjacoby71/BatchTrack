
"""Clean up ProductSKU to have single source of truth for stock

Revision ID: clean_up_product_sku_single_source_truth
Revises: 8b7120014eb3
Create Date: 2025-01-02 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'clean_up_product_sku_single_source_truth'
down_revision = '8b7120014eb3'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Calculate correct current_quantity from history for each SKU
    # This ensures current_quantity reflects the actual sum of all additions/subtractions
    op.execute("""
        UPDATE product_sku 
        SET current_quantity = (
            SELECT COALESCE(SUM(psh.quantity_change), 0)
            FROM product_sku_history psh 
            WHERE psh.sku_id = product_sku.id
        )
    """)
    
    # Step 2: Remove redundant quantity fields that should only exist in history
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        # Remove remaining_quantity - this belongs only in history for FIFO tracking
        batch_op.drop_column('remaining_quantity')
        
        # Remove original_quantity - this belongs only in history
        batch_op.drop_column('original_quantity')
        
        # Remove available_quantity - this should be calculated, not stored
        batch_op.drop_column('available_quantity')
    
    # Step 3: Ensure reserved_quantity defaults are proper
    op.execute("UPDATE product_sku SET reserved_quantity = 0.0 WHERE reserved_quantity IS NULL")
    
    # Step 4: Add indexes to optimize the calculated available_for_sale property
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.create_index('idx_current_reserved_qty', ['current_quantity', 'reserved_quantity'])


def downgrade():
    # Restore the removed columns
    with op.batch_alter_table('product_sku', schema=None) as batch_op:
        batch_op.add_column(sa.Column('remaining_quantity', sa.Float(), default=0.0))
        batch_op.add_column(sa.Column('original_quantity', sa.Float(), default=0.0))
        batch_op.add_column(sa.Column('available_quantity', sa.Float(), default=0.0))
        batch_op.drop_index('idx_current_reserved_qty')
    
    # Restore values from history where possible
    op.execute("""
        UPDATE product_sku 
        SET remaining_quantity = current_quantity,
            original_quantity = current_quantity,
            available_quantity = GREATEST(0, current_quantity - COALESCE(reserved_quantity, 0))
    """)
