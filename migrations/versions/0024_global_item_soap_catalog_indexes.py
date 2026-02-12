"""Ensure global-item indexes for soap bulk-catalog queries.

Synopsis:
Add targeted indexes used by the free soap tools bulk-oils toggle when querying
active ingredient records from the global item library.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import is_postgresql, safe_create_index, safe_drop_index


revision = "0024_global_item_soap_catalog_indexes"
down_revision = "0023_recipe_list_lineage_indexes"
branch_labels = None
depends_on = None


def upgrade():
    # Cross-dialect composite index aligned to tools global-oils listing predicates.
    safe_create_index(
        "ix_global_item_type_archived_name",
        "global_item",
        ["item_type", "is_archived", "name"],
        unique=False,
        verbose=False,
    )

    # PostgreSQL partial index narrows the hot path to active ingredients only.
    if is_postgresql():
        bind = op.get_bind()
        try:
            bind.execute(
                sa.text(
                    "CREATE INDEX IF NOT EXISTS ix_global_item_ingredient_active_name "
                    "ON global_item (name) "
                    "WHERE item_type = 'ingredient' AND is_archived IS FALSE"
                )
            )
        except Exception:
            pass


def downgrade():
    safe_drop_index("ix_global_item_type_archived_name", "global_item", verbose=False)

    if is_postgresql():
        try:
            op.execute("DROP INDEX IF EXISTS ix_global_item_ingredient_active_name")
        except Exception:
            pass
