
"""Add nullable is_organization_owner column to User table

Revision ID: 002_add_is_org_owner_nullable
Revises: dd4b93654b65
Create Date: 2025-07-22 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_is_org_owner_nullable'
down_revision = 'dd4b93654b65'
branch_labels = None
depends_on = None


def upgrade():
    # Add the column as nullable with default False
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_organization_owner', sa.Boolean(), nullable=True, default=False))
    
    # Update existing records to set default value
    op.execute("UPDATE user SET is_organization_owner = 0 WHERE is_organization_owner IS NULL")


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('is_organization_owner')
