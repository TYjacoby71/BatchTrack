
"""Add is_organization_owner column to User table

Revision ID: dd4b93654b65
Revises: 001_add_org_owner
Create Date: 2025-07-22 23:47:05.137345

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dd4b93654b65'
down_revision = '001_add_org_owner'
branch_labels = None
depends_on = None


def upgrade():
    # This migration is empty since the actual column addition
    # is handled by the previous migration (001_add_org_owner)
    pass


def downgrade():
    # This migration is empty since the actual column removal
    # is handled by the previous migration (001_add_org_owner)
    pass
