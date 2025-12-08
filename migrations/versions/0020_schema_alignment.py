"""Placeholder migration.

Schema alignment logic is now part of 0010_recipe_status_drafts.
This placeholder exists solely for Git/GitHub reconciliation.
"""

# revision identifiers, used by Alembic.
revision = '0020_schema_alignment'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade():
    """No-op placeholder."""
    pass


def downgrade():
    """No-op placeholder."""
    pass
