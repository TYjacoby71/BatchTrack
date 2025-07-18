
"""Remove default_units column from organization

Revision ID: remove_default_units_column
Revises: fix_organization_columns
Create Date: 2025-07-18 01:45:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'remove_default_units_column'
down_revision = 'fix_organization_columns'
branch_labels = None
depends_on = None

def upgrade():
    # Remove default_units column from organization table
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.drop_column('default_units')

def downgrade():
    # Add back default_units column
    with op.batch_alter_table('organization', schema=None) as batch_op:
        batch_op.add_column(sa.Column('default_units', sa.String(32), nullable=True))
