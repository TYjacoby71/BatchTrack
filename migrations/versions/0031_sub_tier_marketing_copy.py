"""Subscription tier marketing copy columns.

Synopsis:
Adds nullable marketing presentation fields for pricing/signup card rendering
while preserving the legacy description fallback path.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import safe_add_column, safe_drop_column


revision = "0031_sub_tier_marketing_copy"
down_revision = "0030_marketing_lead_capture"
branch_labels = None
depends_on = None


def upgrade():
    safe_add_column(
        "subscription_tier",
        sa.Column("marketing_tagline", sa.String(length=255), nullable=True),
        verbose=False,
    )
    safe_add_column(
        "subscription_tier",
        sa.Column("marketing_summary", sa.Text(), nullable=True),
        verbose=False,
    )
    safe_add_column(
        "subscription_tier",
        sa.Column("marketing_bullets", sa.Text(), nullable=True),
        verbose=False,
    )


def downgrade():
    safe_drop_column("subscription_tier", "marketing_bullets", verbose=False)
    safe_drop_column("subscription_tier", "marketing_summary", verbose=False)
    safe_drop_column("subscription_tier", "marketing_tagline", verbose=False)

