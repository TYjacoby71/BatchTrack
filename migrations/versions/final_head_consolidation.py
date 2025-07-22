
"""final_head_consolidation

Revision ID: final_head_consolidation
Revises: add_is_organization_owner_column, bd55298f5ebc
Create Date: 2025-07-22 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'final_head_consolidation'
down_revision = ('add_is_organization_owner_column', 'bd55298f5ebc')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration to consolidate all remaining heads
    # No actual schema changes needed
    pass


def downgrade():
    # This is a merge migration to consolidate all remaining heads
    # No actual schema changes needed
    pass
