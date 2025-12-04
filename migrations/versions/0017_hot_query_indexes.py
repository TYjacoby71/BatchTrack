"""add hot-path indexes for product, user, batch, unit, global item

Revision ID: 0017_hot_query_indexes
Revises: 0016_optimize_unit_queries
Create Date: 2025-12-04 21:45:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0017_hot_query_indexes"
down_revision = "0016_optimize_unit_queries"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_product_org_active", "product", ["organization_id", "is_active"])
    op.create_index("ix_user_org_created_at", "user", ["organization_id", "created_at"])
    op.create_index("ix_user_active_type", "user", ["is_active", "user_type"])
    op.create_index(
        "ix_batch_org_status_started_at", "batch", ["organization_id", "status", "started_at"]
    )
    op.create_index(
        "ix_global_item_archive_type_name", "global_item", ["is_archived", "item_type", "name"]
    )
    op.create_index(
        "ix_unit_active_scope_sort", "unit", ["is_active", "is_custom", "unit_type", "name"]
    )


def downgrade():
    op.drop_index("ix_unit_active_scope_sort", table_name="unit")
    op.drop_index("ix_global_item_archive_type_name", table_name="global_item")
    op.drop_index("ix_batch_org_status_started_at", table_name="batch")
    op.drop_index("ix_user_active_type", table_name="user")
    op.drop_index("ix_user_org_created_at", table_name="user")
    op.drop_index("ix_product_org_active", table_name="product")
