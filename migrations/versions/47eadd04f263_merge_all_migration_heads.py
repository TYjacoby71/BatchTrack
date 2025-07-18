"""Merge all migration heads

Revision ID: 47eadd04f263
Revises: 
Create Date: 2025-07-18 01:44:23.462034

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '47eadd04f263'
down_revision = ('remove_default_units', 'make_organization_id_nullable', 'a9764225f9aa', 'fix_developer_users', 'f6a9b50d9a17', '6e0c5e2e1c48')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
