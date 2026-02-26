"""Drop batch.target_version_id and use recipe_id only.

Synopsis:
Removes the duplicate recipe linkage column so batch rows are anchored to
one authoritative recipe version via batch.recipe_id.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    column_exists,
    safe_add_column,
    safe_batch_alter_table,
    safe_create_foreign_key,
    safe_create_index,
    safe_drop_foreign_key,
    safe_drop_index,
    table_exists,
)


revision = "0028_drop_batch_target_version_id"
down_revision = "0027_bot_trap_db_state"
branch_labels = None
depends_on = None


def _backfill_recipe_id_from_target_version() -> None:
    """Ensure every batch points to its concrete recipe row before column drop."""
    if not column_exists("batch", "recipe_id") or not column_exists(
        "batch", "target_version_id"
    ):
        return

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE batch
            SET recipe_id = target_version_id
            WHERE target_version_id IS NOT NULL
              AND (recipe_id IS NULL OR recipe_id <> target_version_id)
              AND EXISTS (
                    SELECT 1
                    FROM recipe
                    WHERE recipe.id = batch.target_version_id
                )
            """
        )
    )


def upgrade():
    if not table_exists("batch") or not column_exists("batch", "target_version_id"):
        return

    _backfill_recipe_id_from_target_version()
    safe_drop_index("ix_batch_target_version_id", table_name="batch", verbose=False)
    safe_drop_foreign_key("fk_batch_target_version_id", "batch", verbose=False)
    with safe_batch_alter_table("batch") as batch_op:
        batch_op.drop_column("target_version_id")


def downgrade():
    if not table_exists("batch"):
        return

    added = safe_add_column(
        "batch",
        sa.Column("target_version_id", sa.Integer(), nullable=True),
        verbose=False,
    )
    if not added and not column_exists("batch", "target_version_id"):
        return

    op.get_bind().execute(
        sa.text(
            """
            UPDATE batch
            SET target_version_id = recipe_id
            WHERE recipe_id IS NOT NULL
            """
        )
    )

    safe_create_foreign_key(
        "fk_batch_target_version_id",
        "batch",
        "recipe",
        ["target_version_id"],
        ["id"],
        verbose=False,
    )
    safe_create_index(
        "ix_batch_target_version_id",
        "batch",
        ["target_version_id"],
        unique=False,
        verbose=False,
    )
