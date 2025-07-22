
"""fix_subscription_migration_conflict

Revision ID: bfc8381314d8
Revises: 40edebb0ba0e
Create Date: 2025-07-19 05:57:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bfc8381314d8'
down_revision = '40edebb0ba0e'
branch_labels = None
depends_on = None


def upgrade():
    # This is a mock migration to satisfy cached references
    # No actual schema changes needed
    pass


def downgrade():
    # This is a mock migration to satisfy cached references
    # No actual schema changes needed
    pass
