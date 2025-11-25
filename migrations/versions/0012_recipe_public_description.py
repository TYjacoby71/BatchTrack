"""0012 recipe public description

Revision ID: 0012_recipe_public_description
Revises: 0011_recipe_marketplace
Create Date: 2025-11-24 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import safe_add_column, safe_drop_column

# revision identifiers, used by Alembic.
revision = '0012_recipe_public_description'
down_revision = '0011_recipe_marketplace'
branch_labels = None
depends_on = None


def upgrade():
    safe_add_column(
        'recipe',
        sa.Column('public_description', sa.Text(), nullable=True)
    )


def downgrade():
    safe_drop_column('recipe', 'public_description')
