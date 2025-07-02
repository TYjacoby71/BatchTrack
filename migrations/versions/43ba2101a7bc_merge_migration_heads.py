"""Merge migration heads

Revision ID: 43ba2101a7bc
Revises: 84207ea041ca, clean_up_product_sku_single_source_truth
Create Date: 2025-07-02 22:35:57.905660

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43ba2101a7bc'
down_revision = ('84207ea041ca', 'clean_up_product_sku_single_source_truth')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
