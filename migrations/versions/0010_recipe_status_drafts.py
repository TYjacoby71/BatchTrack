"""0010 recipe status drafts

Revision ID: 0010_recipe_status_drafts
Revises: 0009_drop_billing_snapshots
Create Date: 2025-11-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import safe_add_column, safe_drop_column


# revision identifiers, used by Alembic.
revision = '0010_recipe_status_drafts'
down_revision = '0009_drop_billing_snapshots'
branch_labels = None
depends_on = None


def upgrade():
    safe_add_column(
        'recipe',
        sa.Column('status', sa.String(length=16), nullable=False, server_default='published')
    )


def downgrade():
    safe_drop_column('recipe', 'status')
