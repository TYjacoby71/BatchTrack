from datetime import datetime, timezone

from ..extensions import db


class AffiliateProfile(db.Model):
    __tablename__ = "affiliate_profile"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True
    )
    referral_code = db.Column(db.String(64), nullable=False, unique=True, index=True)
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default=db.text("true")
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    organization = db.relationship("Organization")
    user = db.relationship("User")
    referrals = db.relationship(
        "AffiliateReferral", back_populates="affiliate_profile", lazy="dynamic"
    )


class AffiliateReferral(db.Model):
    __tablename__ = "affiliate_referral"

    id = db.Column(db.Integer, primary_key=True)
    affiliate_profile_id = db.Column(
        db.Integer, db.ForeignKey("affiliate_profile.id"), nullable=False, index=True
    )
    referrer_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    referrer_organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True
    )
    referred_organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organization.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    referred_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True, index=True
    )
    referred_tier_id = db.Column(
        db.Integer, db.ForeignKey("subscription_tier.id"), nullable=True, index=True
    )
    referral_code = db.Column(db.String(64), nullable=False, index=True)
    referral_source = db.Column(db.String(64), nullable=True)
    commission_percentage_snapshot = db.Column(
        db.Numeric(5, 2), nullable=False, default=0, server_default="0"
    )
    months_eligible = db.Column(
        db.Integer, nullable=False, default=12, server_default="12"
    )
    signed_up_at = db.Column(
        db.DateTime, nullable=False, index=True, default=lambda: datetime.now(timezone.utc)
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    affiliate_profile = db.relationship("AffiliateProfile", back_populates="referrals")
    referrer_user = db.relationship("User", foreign_keys=[referrer_user_id])
    referrer_organization = db.relationship(
        "Organization", foreign_keys=[referrer_organization_id]
    )
    referred_organization = db.relationship(
        "Organization", foreign_keys=[referred_organization_id]
    )
    referred_user = db.relationship("User", foreign_keys=[referred_user_id])
    referred_tier = db.relationship("SubscriptionTier", foreign_keys=[referred_tier_id])
    monthly_earnings = db.relationship(
        "AffiliateMonthlyEarning", back_populates="referral", lazy="dynamic"
    )


class AffiliateMonthlyEarning(db.Model):
    __tablename__ = "affiliate_monthly_earning"

    id = db.Column(db.Integer, primary_key=True)
    affiliate_referral_id = db.Column(
        db.Integer, db.ForeignKey("affiliate_referral.id"), nullable=False, index=True
    )
    referrer_organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True
    )
    referrer_user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    referred_organization_id = db.Column(
        db.Integer, db.ForeignKey("organization.id"), nullable=False, index=True
    )
    earning_month = db.Column(db.Date, nullable=False, index=True)
    currency = db.Column(db.String(3), nullable=False, default="usd", server_default="usd")
    gross_revenue_cents = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    commission_amount_cents = db.Column(
        db.Integer, nullable=False, default=0, server_default="0"
    )
    payout_status = db.Column(
        db.String(32), nullable=False, default="accrued", server_default="accrued"
    )
    payout_reference = db.Column(db.String(128), nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        db.UniqueConstraint(
            "affiliate_referral_id",
            "earning_month",
            name="uq_affiliate_monthly_earning_referral_month",
        ),
    )

    referral = db.relationship("AffiliateReferral", back_populates="monthly_earnings")
    referrer_organization = db.relationship(
        "Organization", foreign_keys=[referrer_organization_id]
    )
    referrer_user = db.relationship("User", foreign_keys=[referrer_user_id])
    referred_organization = db.relationship(
        "Organization", foreign_keys=[referred_organization_id]
    )


class AffiliatePayoutAccount(db.Model):
    __tablename__ = "affiliate_payout_account"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organization.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    payout_provider = db.Column(
        db.String(32), nullable=False, default="stripe", server_default="stripe"
    )
    payout_account_reference = db.Column(db.String(255), nullable=True)
    payout_email = db.Column(db.String(255), nullable=True)
    is_verified = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.text("false")
    )
    metadata_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    organization = db.relationship("Organization")
