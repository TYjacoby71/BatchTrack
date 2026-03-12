"""Durable support feedback note table.

Synopsis:
Adds a dedicated persistent table for customer support note submissions so data
survives deploys and no longer relies on local filesystem JSON files.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import index_exists, safe_create_index, table_exists


revision = "0033_tool_feedback_note_persist"
down_revision = "0032_user_email_uniqueness"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("tool_feedback_note"):
        op.create_table(
            "tool_feedback_note",
            sa.Column("id", sa.String(length=32), primary_key=True),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
            sa.Column("source", sa.String(length=180), nullable=False),
            sa.Column("flow", sa.String(length=64), nullable=False),
            sa.Column("flow_label", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("context", sa.String(length=120), nullable=True),
            sa.Column("page_path", sa.String(length=240), nullable=True),
            sa.Column("page_url", sa.String(length=512), nullable=True),
            sa.Column("contact_email", sa.String(length=254), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("request_json", sa.JSON(), nullable=True),
            sa.Column("user_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    safe_create_index(
        "ix_tool_feedback_note_submitted_at",
        "tool_feedback_note",
        ["submitted_at"],
        verbose=False,
    )
    safe_create_index(
        "ix_tool_feedback_note_source",
        "tool_feedback_note",
        ["source"],
        verbose=False,
    )
    safe_create_index(
        "ix_tool_feedback_note_flow",
        "tool_feedback_note",
        ["flow"],
        verbose=False,
    )
    safe_create_index(
        "ix_tool_feedback_note_contact_email",
        "tool_feedback_note",
        ["contact_email"],
        verbose=False,
    )
    if not index_exists(
        "tool_feedback_note", "ix_tool_feedback_note_source_flow_submitted"
    ):
        op.create_index(
            "ix_tool_feedback_note_source_flow_submitted",
            "tool_feedback_note",
            ["source", "flow", "submitted_at"],
        )


def downgrade():
    if table_exists("tool_feedback_note"):
        op.drop_table("tool_feedback_note")
