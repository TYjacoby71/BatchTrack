
"""batch data storage update

Revision ID: batch_data_storage
Revises: 14343896006d
Create Date: 2024-02-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'batch_data_storage'
down_revision = '14343896006d'
branch_labels = None
depends_on = None

def upgrade():
    # Create new tables
    op.create_table('batch_ingredient',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('ingredient_id', sa.Integer(), nullable=False),
        sa.Column('amount_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
        sa.ForeignKeyConstraint(['ingredient_id'], ['inventory_item.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('batch_container',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('quantity_used', sa.Integer(), nullable=False),
        sa.Column('cost_each', sa.Float()),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], ),
        sa.ForeignKeyConstraint(['container_id'], ['inventory_item.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Update existing batch table
    op.add_column('batch', sa.Column('product_id', sa.Integer(), nullable=True))
    op.add_column('batch', sa.Column('variant_id', sa.Integer(), nullable=True))
    op.add_column('batch', sa.Column('batch_type', sa.String(32), nullable=True))
    op.add_column('batch', sa.Column('yield_amount', sa.Float(), nullable=True))
    op.add_column('batch', sa.Column('yield_unit', sa.String(32), nullable=True))
    op.add_column('batch', sa.Column('completed_at', sa.DateTime(), nullable=True))
    
    # Add foreign key constraints
    op.create_foreign_key(None, 'batch', 'product', ['product_id'], ['id'])
    op.create_foreign_key(None, 'batch', 'product_variation', ['variant_id'], ['id'])
    
    # Rename column for consistency
    op.alter_column('batch', 'start_time', new_column_name='started_at')
    
    # Remove deprecated columns
    op.drop_column('batch', 'timestamp')
    op.drop_column('batch', 'containers')

def downgrade():
    # Remove new tables
    op.drop_table('batch_ingredient')
    op.drop_table('batch_container')
    
    # Restore original batch table structure
    op.drop_constraint(None, 'batch', type_='foreignkey')
    op.drop_constraint(None, 'batch', type_='foreignkey')
    op.add_column('batch', sa.Column('containers', sa.PickleType(), nullable=True))
    op.add_column('batch', sa.Column('timestamp', sa.DateTime(), nullable=True))
    op.alter_column('batch', 'started_at', new_column_name='start_time')
    op.drop_column('batch', 'completed_at')
    op.drop_column('batch', 'yield_unit')
    op.drop_column('batch', 'yield_amount') 
    op.drop_column('batch', 'batch_type')
    op.drop_column('batch', 'variant_id')
    op.drop_column('batch', 'product_id')
