"""Placeholder migration.

Sellability logic now resides in 0010_recipe_status_drafts.
This empty file is left behind so GitHub can reconcile history.
"""

# revision identifiers, used by Alembic.
revision = '0018_recipe_resellable'
down_revision = '0017_hot_query_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """No-op placeholder."""
    pass


def downgrade():
    """No-op placeholder."""
    pass
