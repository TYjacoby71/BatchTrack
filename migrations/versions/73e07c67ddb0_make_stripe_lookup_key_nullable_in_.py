"""Make stripe_lookup_key nullable in pricing_snapshots

Revision ID: 73e07c67ddb0
Revises: 3d46e754118a
Create Date: 2025-07-27 06:21:21.643105

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '73e07c67ddb0'
down_revision = '3d46e754118a'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
