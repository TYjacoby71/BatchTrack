
"""merge heads

Revision ID: dbindex
Revises: update_inventory_types, a489c6978022
Create Date: 2025-05-16 20:33:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dbindex'
down_revision = ('update_inventory_types', 'a489c6978022')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
