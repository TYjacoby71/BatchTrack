"""Add current version flag for recipes.

Synopsis:
Adds is_current to recipe versions and backfills current rows.

Glossary:
- Current version: Active master/variation in a recipe group.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_recipe_current_flag"
down_revision = "0019_recipe_stat_trackers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recipe",
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_recipe_is_current", "recipe", ["is_current"], unique=False)
    op.create_index(
        "ix_recipe_current_branch",
        "recipe",
        ["recipe_group_id", "is_master", "variation_name", "is_current"],
        unique=False,
    )

    op.execute(
        """
        UPDATE recipe
        SET is_current = true
        WHERE id IN (
            SELECT r.id
            FROM recipe r
            JOIN (
                SELECT recipe_group_id, is_master, variation_name, MAX(version_number) AS max_version
                FROM recipe
                WHERE test_sequence IS NULL
                  AND status = 'published'
                  AND is_archived = false
                GROUP BY recipe_group_id, is_master, variation_name
            ) latest
            ON r.recipe_group_id = latest.recipe_group_id
               AND r.is_master = latest.is_master
               AND (
                    r.variation_name = latest.variation_name
                    OR (r.variation_name IS NULL AND latest.variation_name IS NULL)
               )
               AND r.version_number = latest.max_version
            WHERE r.test_sequence IS NULL
              AND r.status = 'published'
              AND r.is_archived = false
        )
        """
    )


def downgrade():
    op.drop_index("ix_recipe_current_branch", table_name="recipe")
    op.drop_index("ix_recipe_is_current", table_name="recipe")
    op.drop_column("recipe", "is_current")
