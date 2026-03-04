"""Marketing lead capture tables.

Synopsis:
Adds canonical marketing contact and source-tagged lead event tables so
waitlist and marketing capture payloads can be filtered by source quickly.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import index_exists, safe_create_index, table_exists


revision = "0030_marketing_lead_capture"
down_revision = "0029_affiliate_prog_foundation"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("marketing_contact"):
        op.create_table(
            "marketing_contact",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("email_normalized", sa.String(length=255), nullable=False),
            sa.Column("first_name", sa.String(length=80), nullable=True),
            sa.Column("last_name", sa.String(length=80), nullable=True),
            sa.Column("business_type", sa.String(length=80), nullable=True),
            sa.Column(
                "status",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            ),
            sa.Column("traits_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "email_normalized",
                name="uq_marketing_contact_email_normalized",
            ),
        )

    if not table_exists("marketing_lead_event"):
        op.create_table(
            "marketing_lead_event",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("contact_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("source_key", sa.String(length=128), nullable=True),
            sa.Column("waitlist_key", sa.String(length=128), nullable=True),
            sa.Column("context", sa.String(length=128), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("tags_json", sa.JSON(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["contact_id"],
                ["marketing_contact.id"],
                name="fk_marketing_lead_event_contact_id",
            ),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_marketing_lead_event_organization_id",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["user.id"],
                name="fk_marketing_lead_event_user_id",
            ),
        )

    safe_create_index(
        "ix_marketing_contact_email_normalized",
        "marketing_contact",
        ["email_normalized"],
        unique=True,
        verbose=False,
    )
    safe_create_index(
        "ix_marketing_lead_event_contact_id",
        "marketing_lead_event",
        ["contact_id"],
        verbose=False,
    )
    safe_create_index(
        "ix_marketing_lead_event_event_type",
        "marketing_lead_event",
        ["event_type"],
        verbose=False,
    )
    safe_create_index(
        "ix_marketing_lead_event_source_key",
        "marketing_lead_event",
        ["source_key"],
        verbose=False,
    )
    safe_create_index(
        "ix_marketing_lead_event_waitlist_key",
        "marketing_lead_event",
        ["waitlist_key"],
        verbose=False,
    )
    safe_create_index(
        "ix_marketing_lead_event_occurred_at",
        "marketing_lead_event",
        ["occurred_at"],
        verbose=False,
    )
    if not index_exists("marketing_lead_event", "ix_marketing_lead_event_source_occurred"):
        op.create_index(
            "ix_marketing_lead_event_source_occurred",
            "marketing_lead_event",
            ["source_key", "occurred_at"],
        )
    if not index_exists(
        "marketing_lead_event", "ix_marketing_lead_event_waitlist_occurred"
    ):
        op.create_index(
            "ix_marketing_lead_event_waitlist_occurred",
            "marketing_lead_event",
            ["waitlist_key", "occurred_at"],
        )


def downgrade():
    if table_exists("marketing_lead_event"):
        op.drop_table("marketing_lead_event")
    if table_exists("marketing_contact"):
        op.drop_table("marketing_contact")
