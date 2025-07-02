"""merge migration heads

Revision ID: 8b7120014eb3
Revises: 
Create Date: 2025-07-02 19:32:16.320689

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b7120014eb3'
down_revision = ('add_default_density', 'remove_requires_containers')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
