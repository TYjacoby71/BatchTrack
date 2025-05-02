
"""add mapped column

Revision ID: add_mapped_column
Revises: add_density_column
Create Date: 2025-05-02 21:57:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_mapped_column'
down_revision = 'add_density_column'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('unit', sa.Column('is_mapped', sa.Boolean(), nullable=True, default=False))

def downgrade():
    op.drop_column('unit', 'is_mapped')
