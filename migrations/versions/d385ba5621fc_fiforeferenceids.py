
"""fiforeferenceids

Revision ID: d385ba5621fc
Revises: 3ddb9fa0db0d
Create Date: 2025-05-20 23:01:13.055

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd385ba5621fc'
down_revision = '3ddb9fa0db0d'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('inventory_history', sa.Column('fifo_reference_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'inventory_history', 'inventory_history', ['fifo_reference_id'], ['id'])
    op.drop_column('inventory_history', 'credited_to_fifo_id')
    op.drop_column('inventory_history', 'source_fifo_id')

def downgrade():
    op.add_column('inventory_history', sa.Column('source_fifo_id', sa.Integer(), nullable=True))
    op.add_column('inventory_history', sa.Column('credited_to_fifo_id', sa.Integer(), nullable=True))
    op.drop_constraint(None, 'inventory_history', type_='foreignkey')
    op.drop_column('inventory_history', 'fifo_reference_id')
