"""Add DB-backed bot trap state tables.

Synopsis:
Creates indexed tables for adaptive IP strike/block state plus durable
identity blocks so middleware no longer depends on filesystem JSON state.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import safe_drop_index, table_exists


revision = "0027_bot_trap_db_state"
down_revision = "0026_user_list_preferences"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("bot_trap_ip_state"):
        op.create_table(
            "bot_trap_ip_state",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ip", sa.String(length=64), nullable=False),
            sa.Column("strike_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("strike_window_started_at", sa.DateTime(), nullable=True),
            sa.Column("last_hit_at", sa.DateTime(), nullable=True),
            sa.Column("blocked_until", sa.DateTime(), nullable=True),
            sa.Column("penalty_level", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_blocked_at", sa.DateTime(), nullable=True),
            sa.Column("last_source", sa.String(length=80), nullable=True),
            sa.Column("last_reason", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("ip", name="uq_bot_trap_ip_state_ip"),
        )
        op.create_index("ix_bot_trap_ip_state_ip", "bot_trap_ip_state", ["ip"])
        op.create_index(
            "ix_bot_trap_ip_state_blocked_until",
            "bot_trap_ip_state",
            ["blocked_until"],
        )
        op.create_index(
            "ix_bot_trap_ip_state_last_hit_at", "bot_trap_ip_state", ["last_hit_at"]
        )

    if not table_exists("bot_trap_identity_block"):
        op.create_table(
            "bot_trap_identity_block",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("block_type", sa.String(length=32), nullable=False),
            sa.Column("value", sa.String(length=255), nullable=False),
            sa.Column("source", sa.String(length=80), nullable=True),
            sa.Column("reason", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "block_type",
                "value",
                name="uq_bot_trap_identity_block_type_value",
            ),
        )
        op.create_index(
            "ix_bot_trap_identity_block_block_type",
            "bot_trap_identity_block",
            ["block_type"],
        )
        op.create_index(
            "ix_bot_trap_identity_block_value", "bot_trap_identity_block", ["value"]
        )
        op.create_index(
            "ix_bot_trap_identity_block_type_value",
            "bot_trap_identity_block",
            ["block_type", "value"],
        )

    if not table_exists("bot_trap_hit"):
        op.create_table(
            "bot_trap_hit",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ip", sa.String(length=64), nullable=True),
            sa.Column("source", sa.String(length=80), nullable=False),
            sa.Column("reason", sa.String(length=80), nullable=False),
            sa.Column("path", sa.String(length=255), nullable=True),
            sa.Column("method", sa.String(length=16), nullable=True),
            sa.Column("user_agent", sa.String(length=160), nullable=True),
            sa.Column("referer", sa.String(length=160), nullable=True),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("extra", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_bot_trap_hit_created_at", "bot_trap_hit", ["created_at"])
        op.create_index("ix_bot_trap_hit_ip", "bot_trap_hit", ["ip"])
        op.create_index("ix_bot_trap_hit_source", "bot_trap_hit", ["source"])
        op.create_index("ix_bot_trap_hit_reason", "bot_trap_hit", ["reason"])
        op.create_index("ix_bot_trap_hit_email", "bot_trap_hit", ["email"])
        op.create_index("ix_bot_trap_hit_user_id", "bot_trap_hit", ["user_id"])


def downgrade():
    if table_exists("bot_trap_hit"):
        safe_drop_index("ix_bot_trap_hit_user_id", table_name="bot_trap_hit", verbose=False)
        safe_drop_index("ix_bot_trap_hit_email", table_name="bot_trap_hit", verbose=False)
        safe_drop_index("ix_bot_trap_hit_reason", table_name="bot_trap_hit", verbose=False)
        safe_drop_index("ix_bot_trap_hit_source", table_name="bot_trap_hit", verbose=False)
        safe_drop_index("ix_bot_trap_hit_ip", table_name="bot_trap_hit", verbose=False)
        safe_drop_index(
            "ix_bot_trap_hit_created_at", table_name="bot_trap_hit", verbose=False
        )
        op.drop_table("bot_trap_hit")

    if table_exists("bot_trap_identity_block"):
        safe_drop_index(
            "ix_bot_trap_identity_block_type_value",
            table_name="bot_trap_identity_block",
            verbose=False,
        )
        safe_drop_index(
            "ix_bot_trap_identity_block_value",
            table_name="bot_trap_identity_block",
            verbose=False,
        )
        safe_drop_index(
            "ix_bot_trap_identity_block_block_type",
            table_name="bot_trap_identity_block",
            verbose=False,
        )
        op.drop_table("bot_trap_identity_block")

    if table_exists("bot_trap_ip_state"):
        safe_drop_index(
            "ix_bot_trap_ip_state_last_hit_at",
            table_name="bot_trap_ip_state",
            verbose=False,
        )
        safe_drop_index(
            "ix_bot_trap_ip_state_blocked_until",
            table_name="bot_trap_ip_state",
            verbose=False,
        )
        safe_drop_index(
            "ix_bot_trap_ip_state_ip",
            table_name="bot_trap_ip_state",
            verbose=False,
        )
        op.drop_table("bot_trap_ip_state")
