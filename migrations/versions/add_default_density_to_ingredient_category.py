
"""Add default_density to ingredient_category

Revision ID: add_default_density
Revises: 3d0ff5b37467
Create Date: 2025-07-01 21:33:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_default_density'
down_revision = '3d0ff5b37467'
branch_labels = None
depends_on = None

def upgrade():
    # Add default_density column to ingredient_category table
    with op.batch_alter_table('ingredient_category', schema=None) as batch_op:
        batch_op.add_column(sa.Column('default_density', sa.Float(), nullable=True))

def downgrade():
    # Remove default_density column from ingredient_category table
    with op.batch_alter_table('ingredient_category', schema=None) as batch_op:
        batch_op.drop_column('default_density')
