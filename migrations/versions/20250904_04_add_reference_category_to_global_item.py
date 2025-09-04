"""
Add reference_category to global_item

Revision ID: 20250904_04a
Revises: 20250904_04
Create Date: 2025-09-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250904_04a'
down_revision = '20250904_04'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('global_item', sa.Column('reference_category', sa.String(length=64), nullable=True))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column('global_item', 'reference_category')
    except Exception:
        pass

