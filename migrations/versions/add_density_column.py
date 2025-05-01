
"""add density column

Revision ID: add_density_column
Revises: add_label_code_column
Create Date: 2025-05-01 06:25:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_density_column'
down_revision = 'add_label_code_column'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('inventory_item', sa.Column('density', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('inventory_item', 'density')
