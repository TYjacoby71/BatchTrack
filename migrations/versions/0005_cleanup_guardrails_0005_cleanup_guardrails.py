
"""0005 cleanup guardrails

Revision ID: 0005_cleanup_guardrails
Revises: 0004_seed_presets
Create Date: 2025-10-21 20:29:06.302261

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_cleanup_guardrails'
down_revision = '0004_seed_presets'
branch_labels = None
depends_on = None


def upgrade():
    # This migration was moved to 0007 - final nullability constraints
    pass</old_str>


def downgrade():
    # Don't reverse the constraint changes - leave them hardened
    # This prevents the back-and-forth nullable changes that cause issues
    pass
