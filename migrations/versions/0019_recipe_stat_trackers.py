"""Add recipe testing and variation trackers.

Synopsis:
Adds recipe testing and variation counters to stats tables.

Glossary:
- Test tracker: Count of test recipes created.
- Variation tracker: Count of non-master recipes created.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0019_recipe_stat_trackers"
down_revision = "0018_recipe_archiving"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_stats",
        sa.Column("master_recipes_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "user_stats",
        sa.Column("variation_recipes_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "user_stats",
        sa.Column("tests_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.add_column(
        "organization_stats",
        sa.Column("total_master_recipes", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "organization_stats",
        sa.Column("total_variation_recipes", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "organization_stats",
        sa.Column("total_test_recipes", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )

    op.add_column(
        "organization_leaderboard_stats",
        sa.Column("most_testing_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "organization_leaderboard_stats",
        sa.Column("most_tests_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_foreign_key(
        "fk_org_leaderboard_most_testing_user",
        "organization_leaderboard_stats",
        "user",
        ["most_testing_user_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint(
        "fk_org_leaderboard_most_testing_user",
        "organization_leaderboard_stats",
        type_="foreignkey",
    )
    op.drop_column("organization_leaderboard_stats", "most_tests_created")
    op.drop_column("organization_leaderboard_stats", "most_testing_user_id")
    op.drop_column("organization_stats", "total_test_recipes")
    op.drop_column("organization_stats", "total_variation_recipes")
    op.drop_column("organization_stats", "total_master_recipes")
    op.drop_column("user_stats", "tests_created")
    op.drop_column("user_stats", "variation_recipes_created")
    op.drop_column("user_stats", "master_recipes_created")
