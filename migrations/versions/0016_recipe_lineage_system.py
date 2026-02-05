"""Add recipe group/version metadata and batch sequences.

Synopsis:
Introduces recipe groups, versioning fields, and batch sequence tracking.

Glossary:
- Recipe group: Container for master/variation lineages.
- Batch sequence: Yearly counter for batch labels.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0016_recipe_lineage_system"
down_revision = "0015_batch_label_counter"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recipe_group",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("prefix", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.UniqueConstraint("organization_id", "name", name="uq_recipe_group_org_name"),
        sa.UniqueConstraint("organization_id", "prefix", name="uq_recipe_group_org_prefix"),
    )
    op.create_index("ix_recipe_group_org", "recipe_group", ["organization_id"], unique=False)

    op.add_column("recipe", sa.Column("recipe_group_id", sa.Integer(), nullable=True))
    op.add_column(
        "recipe",
        sa.Column(
            "is_master",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column("recipe", sa.Column("variation_name", sa.String(length=128), nullable=True))
    op.add_column("recipe", sa.Column("variation_prefix", sa.String(length=8), nullable=True))
    op.add_column(
        "recipe",
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column("recipe", sa.Column("parent_master_id", sa.Integer(), nullable=True))
    op.add_column("recipe", sa.Column("test_sequence", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_recipe_group_id",
        "recipe",
        "recipe_group",
        ["recipe_group_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_recipe_parent_master_id",
        "recipe",
        "recipe",
        ["parent_master_id"],
        ["id"],
    )

    op.create_index("ix_recipe_group_id", "recipe", ["recipe_group_id"], unique=False)
    op.create_index("ix_recipe_parent_master_id", "recipe", ["parent_master_id"], unique=False)
    op.create_index("ix_recipe_is_master", "recipe", ["is_master"], unique=False)
    op.create_index("ix_recipe_version_number", "recipe", ["version_number"], unique=False)
    op.create_index("ix_recipe_test_sequence", "recipe", ["test_sequence"], unique=False)

    op.create_table(
        "batch_sequence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("current_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.UniqueConstraint("organization_id", "year", name="uq_batch_sequence_org_year"),
    )
    op.create_index(
        "ix_batch_sequence_org_year",
        "batch_sequence",
        ["organization_id", "year"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_batch_sequence_org_year", table_name="batch_sequence")
    op.drop_table("batch_sequence")

    op.drop_index("ix_recipe_test_sequence", table_name="recipe")
    op.drop_index("ix_recipe_version_number", table_name="recipe")
    op.drop_index("ix_recipe_is_master", table_name="recipe")
    op.drop_index("ix_recipe_parent_master_id", table_name="recipe")
    op.drop_index("ix_recipe_group_id", table_name="recipe")

    op.drop_constraint("fk_recipe_parent_master_id", "recipe", type_="foreignkey")
    op.drop_constraint("fk_recipe_group_id", "recipe", type_="foreignkey")

    op.drop_column("recipe", "test_sequence")
    op.drop_column("recipe", "parent_master_id")
    op.drop_column("recipe", "version_number")
    op.drop_column("recipe", "variation_prefix")
    op.drop_column("recipe", "variation_name")
    op.drop_column("recipe", "is_master")
    op.drop_column("recipe", "recipe_group_id")

    op.drop_index("ix_recipe_group_org", table_name="recipe_group")
    op.drop_table("recipe_group")
