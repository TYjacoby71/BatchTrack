"""Placeholder migration.

Hot-path indexes now originate in 0010_recipe_status_drafts.
This stub keeps history consistent until the file is deleted.
"""

# revision identifiers, used by Alembic.
revision = '0017_hot_query_indexes'
down_revision = '0016_optimize_unit_queries'
branch_labels = None
depends_on = None


def upgrade():
    """No-op placeholder."""
    pass


def downgrade():
    """No-op placeholder."""
    pass
