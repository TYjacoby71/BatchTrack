"""remove sku from product variation

Revision ID: e2fac90b4ab4
Revises: 61de1bf67d12
Create Date: 2025-06-17 03:49:51.063495

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2fac90b4ab4'
down_revision = '61de1bf67d12'
branch_labels = ('skus',)
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
