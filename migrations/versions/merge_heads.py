
"""merge heads

Revision ID: dbindex
Revises: add_batch_inventory, update_inventory_types
Create Date: 2025-05-16 20:33:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dbindex'
down_revision = ('add_batch_inventory', '923b23b7c7ba')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
