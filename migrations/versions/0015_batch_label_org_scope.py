"""Placeholder migration.

Batch label scope logic now lives in 0010_recipe_status_drafts.
This placeholder exists solely so GitHub can reconcile history.
"""

# revision identifiers, used by Alembic.
revision = '0015_batch_label_org_scope'
down_revision = '0014_batchbot_stack'
branch_labels = None
depends_on = None


def upgrade():
    """No-op placeholder."""
    pass


def downgrade():
    """No-op placeholder."""
    pass
