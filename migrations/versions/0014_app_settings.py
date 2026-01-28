"""Create app_setting table for runtime settings."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0014_app_settings"
down_revision = "0013_item_level_cas_number"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "app_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_app_setting_key", "app_setting", ["key"], unique=True)


def downgrade():
    op.drop_index("ix_app_setting_key", table_name="app_setting")
    op.drop_table("app_setting")
