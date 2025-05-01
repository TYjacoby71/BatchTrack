
"""add batch status tracking

Revision ID: 28f420a8e591
Revises: d3417cb6cf8c
Create Date: 2024-05-01 17:45:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '28f420a8e591'
down_revision = 'd3417cb6cf8c'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('batch', sa.Column('status_reason', sa.Text(), nullable=True))
    op.add_column('batch', sa.Column('failed_at', sa.DateTime(), nullable=True))
    op.add_column('batch', sa.Column('cancelled_at', sa.DateTime(), nullable=True))
    op.add_column('batch', sa.Column('inventory_credited', sa.Boolean(), nullable=False, server_default='0'))

def downgrade():
    op.drop_column('batch', 'status_reason')
    op.drop_column('batch', 'failed_at')
    op.drop_column('batch', 'cancelled_at')
    op.drop_column('batch', 'inventory_credited')
