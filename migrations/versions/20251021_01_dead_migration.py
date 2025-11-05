
"""dead migration

Revision ID: 20251021_01
Revises: 0005_cleanup_guardrails
Create Date: 2024-10-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251021_01'
down_revision = '0005_cleanup_guardrails'
branch_labels = None
depends_on = None


def upgrade():
    """Dead migration - no operations performed"""
    pass


def downgrade():
    """Dead migration - no operations performed"""
    pass
