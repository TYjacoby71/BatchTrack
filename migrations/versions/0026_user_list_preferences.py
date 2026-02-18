"""Add DB-backed list preferences to user preferences.

Synopsis:
Adds user_preferences.list_preferences JSON payload to persist per-user table
and filter UI state across sessions/devices.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import safe_add_column, safe_drop_column


revision = "0026_user_list_preferences"
down_revision = "0025_inventory_item_is_tracked"
branch_labels = None
depends_on = None


def upgrade():
    safe_add_column(
        "user_preferences",
        sa.Column("list_preferences", sa.JSON(), nullable=True),
        verbose=False,
    )


def downgrade():
    safe_drop_column("user_preferences", "list_preferences", verbose=False)
