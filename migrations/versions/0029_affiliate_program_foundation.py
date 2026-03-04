"""Affiliate program foundation schema.

Synopsis:
Adds tier commission percentages plus core affiliate tracking tables used by
settings, organization, and developer affiliate dashboards.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from migrations.postgres_helpers import (
    safe_add_column,
    safe_create_index,
    safe_drop_column,
    table_exists,
)


revision = "0029_affiliate_prog_foundation"
down_revision = "0028_drop_batch_target_ver_id"
branch_labels = None
depends_on = None


def upgrade():
    safe_add_column(
        "subscription_tier",
        sa.Column(
            "commission_percentage",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="0",
        ),
        verbose=False,
    )

    if not table_exists("affiliate_profile"):
        op.create_table(
            "affiliate_profile",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("referral_code", sa.String(length=64), nullable=False),
            sa.Column(
                "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_affiliate_profile_organization_id",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["user.id"], name="fk_affiliate_profile_user_id"
            ),
            sa.UniqueConstraint("user_id", name="uq_affiliate_profile_user_id"),
            sa.UniqueConstraint(
                "referral_code", name="uq_affiliate_profile_referral_code"
            ),
        )
        op.create_index(
            "ix_affiliate_profile_organization_id",
            "affiliate_profile",
            ["organization_id"],
        )
        op.create_index("ix_affiliate_profile_user_id", "affiliate_profile", ["user_id"])
        op.create_index(
            "ix_affiliate_profile_referral_code",
            "affiliate_profile",
            ["referral_code"],
        )

    if not table_exists("affiliate_referral"):
        op.create_table(
            "affiliate_referral",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("affiliate_profile_id", sa.Integer(), nullable=False),
            sa.Column("referrer_user_id", sa.Integer(), nullable=False),
            sa.Column("referrer_organization_id", sa.Integer(), nullable=False),
            sa.Column("referred_organization_id", sa.Integer(), nullable=False),
            sa.Column("referred_user_id", sa.Integer(), nullable=True),
            sa.Column("referred_tier_id", sa.Integer(), nullable=True),
            sa.Column("referral_code", sa.String(length=64), nullable=False),
            sa.Column("referral_source", sa.String(length=64), nullable=True),
            sa.Column("billing_mode_snapshot", sa.String(length=32), nullable=True),
            sa.Column("billing_cycle_snapshot", sa.String(length=32), nullable=True),
            sa.Column(
                "commission_percentage_snapshot",
                sa.Numeric(5, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "months_eligible",
                sa.Integer(),
                nullable=False,
                server_default="12",
            ),
            sa.Column("signed_up_at", sa.DateTime(), nullable=False),
            sa.Column("churned_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["affiliate_profile_id"],
                ["affiliate_profile.id"],
                name="fk_affiliate_referral_affiliate_profile_id",
            ),
            sa.ForeignKeyConstraint(
                ["referrer_user_id"],
                ["user.id"],
                name="fk_affiliate_referral_referrer_user_id",
            ),
            sa.ForeignKeyConstraint(
                ["referrer_organization_id"],
                ["organization.id"],
                name="fk_affiliate_referral_referrer_organization_id",
            ),
            sa.ForeignKeyConstraint(
                ["referred_organization_id"],
                ["organization.id"],
                name="fk_affiliate_referral_referred_organization_id",
            ),
            sa.ForeignKeyConstraint(
                ["referred_user_id"],
                ["user.id"],
                name="fk_affiliate_referral_referred_user_id",
            ),
            sa.ForeignKeyConstraint(
                ["referred_tier_id"],
                ["subscription_tier.id"],
                name="fk_affiliate_referral_referred_tier_id",
            ),
            sa.UniqueConstraint(
                "referred_organization_id",
                name="uq_affiliate_referral_referred_organization_id",
            ),
        )
        op.create_index(
            "ix_affiliate_referral_affiliate_profile_id",
            "affiliate_referral",
            ["affiliate_profile_id"],
        )
        op.create_index(
            "ix_affiliate_referral_referrer_user_id",
            "affiliate_referral",
            ["referrer_user_id"],
        )
        op.create_index(
            "ix_affiliate_referral_referrer_org_id",
            "affiliate_referral",
            ["referrer_organization_id"],
        )
        op.create_index(
            "ix_affiliate_referral_referred_org_id",
            "affiliate_referral",
            ["referred_organization_id"],
        )
        op.create_index(
            "ix_affiliate_referral_referral_code",
            "affiliate_referral",
            ["referral_code"],
        )
        op.create_index(
            "ix_affiliate_referral_signed_up_at",
            "affiliate_referral",
            ["signed_up_at"],
        )
        op.create_index(
            "ix_affiliate_referral_churned_at",
            "affiliate_referral",
            ["churned_at"],
        )
    else:
        safe_add_column(
            "affiliate_referral",
            sa.Column("billing_mode_snapshot", sa.String(length=32), nullable=True),
            verbose=False,
        )
        safe_add_column(
            "affiliate_referral",
            sa.Column("billing_cycle_snapshot", sa.String(length=32), nullable=True),
            verbose=False,
        )
        safe_add_column(
            "affiliate_referral",
            sa.Column("churned_at", sa.DateTime(), nullable=True),
            verbose=False,
        )
        safe_create_index(
            "affiliate_referral",
            "ix_affiliate_referral_churned_at",
            ["churned_at"],
            verbose=False,
        )

    if not table_exists("affiliate_monthly_earning"):
        op.create_table(
            "affiliate_monthly_earning",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("affiliate_referral_id", sa.Integer(), nullable=False),
            sa.Column("referrer_organization_id", sa.Integer(), nullable=False),
            sa.Column("referrer_user_id", sa.Integer(), nullable=False),
            sa.Column("referred_organization_id", sa.Integer(), nullable=False),
            sa.Column("earning_month", sa.Date(), nullable=False),
            sa.Column(
                "currency", sa.String(length=3), nullable=False, server_default="usd"
            ),
            sa.Column(
                "gross_revenue_cents",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "commission_amount_cents",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "payout_status",
                sa.String(length=32),
                nullable=False,
                server_default="accrued",
            ),
            sa.Column("payout_reference", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["affiliate_referral_id"],
                ["affiliate_referral.id"],
                name="fk_affiliate_monthly_earning_referral_id",
            ),
            sa.ForeignKeyConstraint(
                ["referrer_organization_id"],
                ["organization.id"],
                name="fk_affiliate_monthly_earning_referrer_organization_id",
            ),
            sa.ForeignKeyConstraint(
                ["referrer_user_id"],
                ["user.id"],
                name="fk_affiliate_monthly_earning_referrer_user_id",
            ),
            sa.ForeignKeyConstraint(
                ["referred_organization_id"],
                ["organization.id"],
                name="fk_affiliate_monthly_earning_referred_organization_id",
            ),
            sa.UniqueConstraint(
                "affiliate_referral_id",
                "earning_month",
                name="uq_affiliate_monthly_earning_referral_month",
            ),
        )
        op.create_index(
            "ix_affiliate_monthly_earning_referral_id",
            "affiliate_monthly_earning",
            ["affiliate_referral_id"],
        )
        op.create_index(
            "ix_affiliate_monthly_earning_referrer_org_id",
            "affiliate_monthly_earning",
            ["referrer_organization_id"],
        )
        op.create_index(
            "ix_affiliate_monthly_earning_referrer_user_id",
            "affiliate_monthly_earning",
            ["referrer_user_id"],
        )
        op.create_index(
            "ix_affiliate_monthly_earning_referred_org_id",
            "affiliate_monthly_earning",
            ["referred_organization_id"],
        )
        op.create_index(
            "ix_affiliate_monthly_earning_earning_month",
            "affiliate_monthly_earning",
            ["earning_month"],
        )

    if not table_exists("affiliate_payout_account"):
        op.create_table(
            "affiliate_payout_account",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column(
                "payout_provider",
                sa.String(length=32),
                nullable=False,
                server_default="stripe",
            ),
            sa.Column("payout_account_reference", sa.String(length=255), nullable=True),
            sa.Column("payout_email", sa.String(length=255), nullable=True),
            sa.Column(
                "is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("metadata_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["organization_id"],
                ["organization.id"],
                name="fk_affiliate_payout_account_organization_id",
            ),
            sa.UniqueConstraint(
                "organization_id", name="uq_affiliate_payout_account_organization_id"
            ),
        )
        op.create_index(
            "ix_affiliate_payout_account_organization_id",
            "affiliate_payout_account",
            ["organization_id"],
        )


def downgrade():
    if table_exists("affiliate_payout_account"):
        op.drop_table("affiliate_payout_account")

    if table_exists("affiliate_monthly_earning"):
        op.drop_table("affiliate_monthly_earning")

    if table_exists("affiliate_referral"):
        op.drop_table("affiliate_referral")

    if table_exists("affiliate_profile"):
        op.drop_table("affiliate_profile")

    safe_drop_column("subscription_tier", "commission_percentage", verbose=False)
