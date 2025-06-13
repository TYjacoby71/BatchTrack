"""merge_migration_heads

Revision ID: 26ef12681840
Revises: 146ce72829eb, fix_organization_column
Create Date: 2025-06-13 20:50:57.602290

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26ef12681840'
down_revision = ('146ce72829eb', 'fix_organization_column')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
