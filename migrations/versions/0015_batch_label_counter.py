"""Add batch_label_counter table for sequential labels."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_batch_label_counter"
down_revision = "0014_app_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "batch_label_counter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("next_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.UniqueConstraint(
            "organization_id",
            "prefix",
            "year",
            name="uq_batch_label_counter_org_prefix_year",
        ),
    )
    op.create_index(
        "ix_batch_label_counter_org_prefix_year",
        "batch_label_counter",
        ["organization_id", "prefix", "year"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_batch_label_counter_org_prefix_year",
        table_name="batch_label_counter",
    )
    op.drop_table("batch_label_counter")
