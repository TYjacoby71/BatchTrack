"""Merge migration heads

Revision ID: 1e08f080c0a6
Revises: 
Create Date: 2025-05-30 19:43:05.232120

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e08f080c0a6'
down_revision = ('4ff7f4b5ea62', 'add_unit_to_history')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
