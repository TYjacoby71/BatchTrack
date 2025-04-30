
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
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], name='fk_batch_ingredient_batch_id'),
        sa.ForeignKeyConstraint(['ingredient_id'], ['inventory_item.id'], name='fk_batch_ingredient_ingredient_id'),
        sa.PrimaryKeyConstraint('id', name='pk_batch_ingredient')
    )

    op.create_table('batch_container',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('container_id', sa.Integer(), nullable=False),
        sa.Column('quantity_used', sa.Integer(), nullable=False),
        sa.Column('cost_each', sa.Float()),
        sa.ForeignKeyConstraint(['batch_id'], ['batch.id'], name='fk_batch_container_batch_id'),
        sa.ForeignKeyConstraint(['container_id'], ['inventory_item.id'], name='fk_batch_container_container_id'),
        sa.PrimaryKeyConstraint('id', name='pk_batch_container')
    )
    
    # Update existing batch table
    with op.batch_alter_table('batch') as batch_op:
        batch_op.add_column(sa.Column('product_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('variant_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('batch_type', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('yield_amount', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('yield_unit', sa.String(32), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))
        batch_op.create_foreign_key('fk_batch_product_id', 'product', ['product_id'], ['id'])
        batch_op.create_foreign_key('fk_batch_variant_id', 'product_variation', ['variant_id'], ['id'])
        batch_op.alter_column('start_time', new_column_name='started_at')
        batch_op.drop_column('timestamp')
        batch_op.drop_column('containers')

def downgrade():
    # Remove new tables
    op.drop_table('batch_ingredient')
    op.drop_table('batch_container')
    
    # Restore original batch table structure
    with op.batch_alter_table('batch') as batch_op:
        batch_op.drop_constraint('fk_batch_product_id', type_='foreignkey')
        batch_op.drop_constraint('fk_batch_variant_id', type_='foreignkey')
        batch_op.add_column(sa.Column('containers', sa.PickleType(), nullable=True))
        batch_op.add_column(sa.Column('timestamp', sa.DateTime(), nullable=True))
        batch_op.alter_column('started_at', new_column_name='start_time')
        batch_op.drop_column('completed_at')
        batch_op.drop_column('yield_unit')
        batch_op.drop_column('yield_amount')
        batch_op.drop_column('batch_type')
        batch_op.drop_column('variant_id')
        batch_op.drop_column('product_id')
