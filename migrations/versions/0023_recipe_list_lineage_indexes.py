"""Add recipe list and lineage indexes.

Synopsis:
Create composite indexes for recipe list filtering and lineage event queries.
"""

from __future__ import annotations

from alembic import op


revision = "0023_recipe_list_lineage_indexes"
down_revision = "0022_integer_base_quantities"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_recipe_list_page",
        "recipe",
        [
            "organization_id",
            "is_archived",
            "is_current",
            "parent_recipe_id",
            "test_sequence",
            "name",
        ],
    )
    op.create_index(
        "ix_recipe_root_created_at",
        "recipe",
        ["root_recipe_id", "created_at"],
    )
    op.create_index(
        "ix_recipe_lineage_recipe_created_at",
        "recipe_lineage",
        ["recipe_id", "created_at"],
    )
    op.create_index(
        "ix_recipe_lineage_recipe_event_created_at",
        "recipe_lineage",
        ["recipe_id", "event_type", "created_at"],
    )


def downgrade():
    op.drop_index(
        "ix_recipe_lineage_recipe_event_created_at",
        table_name="recipe_lineage",
    )
    op.drop_index(
        "ix_recipe_lineage_recipe_created_at",
        table_name="recipe_lineage",
    )
    op.drop_index(
        "ix_recipe_root_created_at",
        table_name="recipe",
    )
    op.drop_index(
        "ix_recipe_list_page",
        table_name="recipe",
    )
