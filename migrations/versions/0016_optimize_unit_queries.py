"""0016 optimize unit queries

Revision ID: 0016_optimize_unit_queries
Revises: 0015_batch_label_org_scope
Create Date: 2025-12-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0016_optimize_unit_queries"
down_revision = "0015_batch_label_org_scope"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_unit_active_scope_sort",
        "unit",
        ["is_active", "is_custom", "unit_type", "name"],
        unique=False,
    )
    op.create_index(
        "ix_unit_custom_org_scope",
        "unit",
        ["organization_id", "is_active", "is_custom", "unit_type", "name"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_unit_custom_org_scope", table_name="unit")
    op.drop_index("ix_unit_active_scope_sort", table_name="unit")
