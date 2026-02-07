"""Add recipe archiving fields.

Synopsis:
Introduces is_archived, archived_at, and archived_by tracking.

Glossary:
- Archived: Soft-hidden recipe state.
- archived_by: User ID that initiated archiving.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_recipe_archiving"
down_revision = "0017_batch_lineage_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recipe",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("recipe", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("recipe", sa.Column("archived_by", sa.Integer(), nullable=True))
    op.create_index("ix_recipe_is_archived", "recipe", ["is_archived"], unique=False)
    op.create_foreign_key(
        "fk_recipe_archived_by",
        "recipe",
        "user",
        ["archived_by"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_recipe_archived_by", "recipe", type_="foreignkey")
    op.drop_index("ix_recipe_is_archived", table_name="recipe")
    op.drop_column("recipe", "archived_by")
    op.drop_column("recipe", "archived_at")
    op.drop_column("recipe", "is_archived")
