"""Placeholder migration.

This file is intentionally empty because its schema changes were
folded into 0010_recipe_status_drafts. It remains only so Git can
reconcile history before permanent removal.
"""

# revision identifiers, used by Alembic.
revision = '0011_recipe_marketplace'
down_revision = '0010_recipe_status_drafts'
branch_labels = None
depends_on = None


def upgrade():
    """No-op placeholder."""
    pass


def downgrade():
    """No-op placeholder."""
    pass
