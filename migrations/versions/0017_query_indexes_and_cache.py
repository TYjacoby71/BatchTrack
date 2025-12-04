"""0017 add composite indexes for hot queries

Revision ID: 0017_query_indexes_and_cache
Revises: 0016_optimize_unit_queries
Create Date: 2025-12-04 00:00:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "0017_query_indexes_and_cache"
down_revision = "0016_optimize_unit_queries"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_product_org_active_name",
        "product",
        ["organization_id", "is_active", "name"],
        unique=False,
    )
    op.create_index(
        "ix_user_org_created_at",
        "user",
        ["organization_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_org_active",
        "user",
        ["organization_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "ix_user_active_type",
        "user",
        ["is_active", "user_type"],
        unique=False,
    )
    op.create_index(
        "ix_global_item_active_sort",
        "global_item",
        ["is_archived", "item_type", "name"],
        unique=False,
    )
    op.create_index(
        "ix_recipe_public_listing",
        "recipe",
        ["is_public", "status", "marketplace_status", "marketplace_blocked", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_recipe_org_public_listing",
        "recipe",
        [
            "organization_id",
            "is_public",
            "status",
            "marketplace_status",
            "marketplace_blocked",
            "updated_at",
        ],
        unique=False,
    )
    op.create_index(
        "ix_batch_org_status_started_at",
        "batch",
        ["organization_id", "status", "started_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_batch_org_status_started_at", table_name="batch")
    op.drop_index("ix_recipe_org_public_listing", table_name="recipe")
    op.drop_index("ix_recipe_public_listing", table_name="recipe")
    op.drop_index("ix_global_item_active_sort", table_name="global_item")
    op.drop_index("ix_user_active_type", table_name="user")
    op.drop_index("ix_user_org_active", table_name="user")
    op.drop_index("ix_user_org_created_at", table_name="user")
    op.drop_index("ix_product_org_active_name", table_name="product")
