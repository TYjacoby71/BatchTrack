"""Add batch_queue_item table for production queue."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0014_batch_queue_items"
down_revision = "0013_item_level_cas_number"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "batch_queue_item",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("recipe_id", sa.Integer, sa.ForeignKey("recipe.id"), nullable=False),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("batch.id"), nullable=True),
        sa.Column("queue_code", sa.String(length=32), nullable=False),
        sa.Column("queue_position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scale", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("batch_type", sa.String(length=32), nullable=False, server_default="ingredient"),
        sa.Column("projected_yield", sa.Float, nullable=True),
        sa.Column("projected_yield_unit", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("plan_snapshot", sa.JSON, nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("user.id"), nullable=True),
        sa.Column("organization_id", sa.Integer, sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("cancelled_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_batch_queue_item_queue_code", "batch_queue_item", ["queue_code"])
    op.create_index("ix_batch_queue_item_created_at", "batch_queue_item", ["created_at"])
    op.create_index(
        "ix_batch_queue_org_status_created",
        "batch_queue_item",
        ["organization_id", "status", "created_at"],
    )


def downgrade():
    op.drop_index("ix_batch_queue_org_status_created", table_name="batch_queue_item")
    op.drop_index("ix_batch_queue_item_created_at", table_name="batch_queue_item")
    op.drop_index("ix_batch_queue_item_queue_code", table_name="batch_queue_item")
    op.drop_table("batch_queue_item")
