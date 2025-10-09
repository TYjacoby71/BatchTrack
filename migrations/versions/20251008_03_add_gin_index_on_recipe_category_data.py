"""
Add optional GIN index on recipe.category_data for ad-hoc queries
"""

from alembic import op
from sqlalchemy import inspect

revision = '20251008_3'
down_revision = '20251008_2'
branch_labels = None
depends_on = None


def table_exists(table_name):
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    if not table_exists('recipe'):
        return
    try:
        # PostgreSQL-specific: create GIN index on JSONB cast
        op.execute("CREATE INDEX IF NOT EXISTS ix_recipe_category_data_gin ON recipe USING GIN ((category_data::jsonb))")
    except Exception:
        # Non-Postgres or permissions issues; ignore
        pass


def downgrade():
    try:
        op.execute("DROP INDEX IF EXISTS ix_recipe_category_data_gin")
    except Exception:
        pass
