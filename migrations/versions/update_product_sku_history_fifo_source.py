
"""Update ProductSKUHistory with fifo_source field

Revision ID: update_product_sku_history_fifo_source
Revises: add_product_sku_history_fields
Create Date: 2025-01-26 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'update_product_sku_history_fifo_source'
down_revision = 'add_product_sku_history_fields'
branch_labels = None
depends_on = None

def upgrade():
    # Add fifo_source column
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fifo_source', sa.String(length=128), nullable=True))
        
        # Drop the used_for_batch_id foreign key and column
        batch_op.drop_constraint('fk_product_sku_history_used_for_batch', type_='foreignkey')
        batch_op.drop_column('used_for_batch_id')
        
        # Add index for fifo_source
        batch_op.create_index('idx_fifo_source', ['fifo_source'], unique=False)

def downgrade():
    # Remove fifo_source and restore used_for_batch_id
    with op.batch_alter_table('product_sku_history', schema=None) as batch_op:
        batch_op.drop_index('idx_fifo_source')
        batch_op.drop_column('fifo_source')
        
        # Restore used_for_batch_id
        batch_op.add_column(sa.Column('used_for_batch_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_product_sku_history_used_for_batch', 'batch', ['used_for_batch_id'], ['id'])
