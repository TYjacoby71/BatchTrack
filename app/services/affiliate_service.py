"""Affiliate program service helpers.

Synopsis:
Centralizes affiliate link generation, referral attribution, and dashboard
summary payloads for settings, organization, and developer surfaces.
"""

from __future__ import annotations

import re
import secrets
from datetime import date
from typing import Any

from sqlalchemy import func, inspect

from ..extensions import db
from ..models import Organization, User
from ..models.affiliate import (
    AffiliateMonthlyEarning,
    AffiliatePayoutAccount,
    AffiliateProfile,
    AffiliateReferral,
)
from ..utils.permissions import has_permission
from ..utils.timezone_utils import TimezoneUtils


class AffiliateService:
    COOKIE_NAME = "bt_affiliate_ref"
    COOKIE_MAX_AGE_SECONDS = 90 * 24 * 60 * 60
    _CODE_PATTERN = re.compile(r"^[a-z0-9_-]{4,64}$")

    @classmethod
    def _schema_ready(cls) -> bool:
        try:
            inspector = inspect(db.engine)
            return inspector.has_table("affiliate_profile") and inspector.has_table(
                "affiliate_referral"
            )
        except Exception:
            return False

    @classmethod
    def normalize_referral_code(cls, value: str | None) -> str | None:
        cleaned = (value or "").strip().lower()
        if not cleaned:
            return None
        if not cls._CODE_PATTERN.fullmatch(cleaned):
            return None
        return cleaned

    @classmethod
    def extract_referral_code_from_request(cls, request) -> str | None:
        if request is None:
            return None
        for candidate in (
            request.args.get("ref"),
            request.form.get("ref"),
            request.cookies.get(cls.COOKIE_NAME),
        ):
            normalized = cls.normalize_referral_code(candidate)
            if normalized:
                return normalized
        return None

    @classmethod
    def set_referral_cookie(
        cls,
        response,
        referral_code: str | None,
        *,
        secure: bool = False,
    ):
        if response is None:
            return response
        normalized = cls.normalize_referral_code(referral_code)
        if not normalized:
            return response
        response.set_cookie(
            cls.COOKIE_NAME,
            normalized,
            max_age=cls.COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            samesite="Lax",
            secure=bool(secure),
        )
        return response

    @classmethod
    def _generate_unique_referral_code(cls) -> str:
        while True:
            candidate = f"aff_{secrets.token_urlsafe(8).replace('-', '').replace('_', '').lower()[:12]}"
            if (
                AffiliateProfile.query.filter(
                    func.lower(AffiliateProfile.referral_code) == candidate
                ).first()
                is None
            ):
                return candidate

    @classmethod
    def rotate_profile_referral_code(
        cls, profile: AffiliateProfile | None, *, auto_commit: bool = True
    ) -> AffiliateProfile | None:
        if not profile or not cls._schema_ready():
            return None
        profile.referral_code = cls._generate_unique_referral_code()
        profile.updated_at = TimezoneUtils.utc_now()
        if auto_commit:
            db.session.commit()
        return profile

    @classmethod
    def get_or_create_affiliate_profile(
        cls, user: User | None, *, auto_commit: bool = True
    ) -> AffiliateProfile | None:
        if not user or user.user_type != "customer" or not user.organization_id:
            return None
        if not cls._schema_ready():
            return None

        profile = AffiliateProfile.query.filter_by(user_id=user.id).first()
        if profile:
            return profile

        profile = AffiliateProfile(
            organization_id=user.organization_id,
            user_id=user.id,
            referral_code=cls._generate_unique_referral_code(),
            is_active=True,
        )
        db.session.add(profile)
        if auto_commit:
            db.session.commit()
        return profile

    @classmethod
    def build_referral_link(cls, user: User | None, *, base_url: str) -> str | None:
        profile = cls.get_or_create_affiliate_profile(user, auto_commit=True)
        if not profile:
            return None
        root = (base_url or "").rstrip("/")
        return f"{root}/auth/signup?ref={profile.referral_code}"

    @staticmethod
    def _format_currency_cents(amount_cents: int | None) -> str:
        amount = int(amount_cents or 0)
        return f"${amount / 100:,.2f}"

    @staticmethod
    def _redacted_first_name(org: Organization | None) -> str:
        if not org:
            return "Unknown"
        owner = org.owner
        if owner and owner.first_name:
            return owner.first_name.strip()[:1] + "***"
        contact = (org.contact_email or "").strip()
        if "@" in contact and contact.split("@", 1)[0]:
            return contact.split("@", 1)[0][:1] + "***"
        name = (org.name or "").strip()
        if name:
            return name.split(" ", 1)[0][:1] + "***"
        return "Unknown"

    @classmethod
    def register_referred_organization(
        cls,
        *,
        referral_code: str | None,
        referred_organization: Organization | None,
        referred_user: User | None = None,
        signup_source: str | None = None,
        auto_commit: bool = False,
    ) -> AffiliateReferral | None:
        if not referred_organization or not cls._schema_ready():
            return None

        normalized = cls.normalize_referral_code(referral_code)
        if not normalized:
            return None

        profile = AffiliateProfile.query.filter(
            func.lower(AffiliateProfile.referral_code) == normalized
        ).first()
        if not profile or not profile.is_active:
            return None

        if profile.organization_id == referred_organization.id:
            return None

        existing = AffiliateReferral.query.filter_by(
            referred_organization_id=referred_organization.id
        ).first()
        if existing:
            return existing

        commission_snapshot = float(
            getattr(referred_organization.tier, "commission_percentage", 0) or 0
        )
        referral = AffiliateReferral(
            affiliate_profile_id=profile.id,
            referrer_user_id=profile.user_id,
            referrer_organization_id=profile.organization_id,
            referred_organization_id=referred_organization.id,
            referred_user_id=getattr(referred_user, "id", None),
            referred_tier_id=getattr(referred_organization, "subscription_tier_id", None),
            referral_code=normalized,
            referral_source=signup_source or "signup",
            commission_percentage_snapshot=commission_snapshot,
            months_eligible=12,
            signed_up_at=TimezoneUtils.utc_now(),
        )
        db.session.add(referral)
        if auto_commit:
            db.session.commit()
        return referral

    @classmethod
    def build_user_settings_context(
        cls,
        user: User | None,
        *,
        base_url: str,
        page: int = 1,
        per_page: int = 10,
    ) -> dict[str, Any]:
        default_payload = {
            "enabled": False,
            "can_generate_link": False,
            "referral_link": None,
            "referral_code": None,
            "total_signups": 0,
            "total_commission_cents": 0,
            "total_commission_display": "$0.00",
            "monthly_commission_cents": 0,
            "monthly_commission_display": "$0.00",
            "referrals": [],
            "page": page,
            "pages": 1,
            "has_prev": False,
            "has_next": False,
            "reason": None,
        }
        if not user or user.user_type != "customer" or not user.organization_id:
            default_payload["reason"] = "Affiliate program is available to organization members only."
            return default_payload

        can_view = has_permission(user, "affiliates.view") or has_permission(
            user, "organization.manage_billing"
        )
        can_generate = has_permission(user, "affiliates.generate_links") or has_permission(
            user, "organization.manage_billing"
        )
        if not can_view:
            default_payload["reason"] = "You do not currently have affiliate access."
            return default_payload

        if not cls._schema_ready():
            default_payload["reason"] = "Affiliate schema has not been migrated yet."
            return default_payload

        profile = cls.get_or_create_affiliate_profile(user, auto_commit=True)
        referral_link = cls.build_referral_link(user, base_url=base_url) if can_generate else None

        query = AffiliateReferral.query.filter_by(referrer_user_id=user.id).order_by(
            AffiliateReferral.signed_up_at.desc()
        )
        pagination = query.paginate(
            page=max(1, int(page)),
            per_page=max(1, min(int(per_page), 50)),
            error_out=False,
        )

        referral_rows = []
        for referral in pagination.items:
            referred_org = referral.referred_organization
            referral_rows.append(
                {
                    "first_name_redacted": cls._redacted_first_name(referred_org),
                    "signed_up_at": referral.signed_up_at,
                    "referral_code": referral.referral_code,
                    "tier_name": (
                        referred_org.tier.name
                        if referred_org and getattr(referred_org, "tier", None)
                        else "N/A"
                    ),
                }
            )

        total_commission_cents = (
            db.session.query(func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0))
            .filter(AffiliateMonthlyEarning.referrer_user_id == user.id)
            .scalar()
            or 0
        )
        today = TimezoneUtils.utc_now().date()
        month_start = date(today.year, today.month, 1)
        monthly_commission_cents = (
            db.session.query(func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0))
            .filter(
                AffiliateMonthlyEarning.referrer_user_id == user.id,
                AffiliateMonthlyEarning.earning_month >= month_start,
            )
            .scalar()
            or 0
        )

        return {
            "enabled": True,
            "can_generate_link": can_generate,
            "referral_link": referral_link,
            "referral_code": profile.referral_code if profile else None,
            "total_signups": pagination.total,
            "total_commission_cents": int(total_commission_cents),
            "total_commission_display": cls._format_currency_cents(total_commission_cents),
            "monthly_commission_cents": int(monthly_commission_cents),
            "monthly_commission_display": cls._format_currency_cents(monthly_commission_cents),
            "referrals": referral_rows,
            "page": pagination.page,
            "pages": max(1, pagination.pages),
            "has_prev": pagination.has_prev,
            "has_next": pagination.has_next,
            "reason": None,
        }

    @classmethod
    def build_organization_dashboard_context(
        cls, organization: Organization | None, *, page: int = 1, per_page: int = 10
    ) -> dict[str, Any]:
        payload = {
            "enabled": False,
            "total_referrals": 0,
            "active_referred_organizations": 0,
            "total_commission_cents": 0,
            "total_commission_display": "$0.00",
            "commission_percentage": 0.0,
            "by_user_rows": [],
            "referrals": [],
            "page": page,
            "pages": 1,
            "has_prev": False,
            "has_next": False,
        }
        if not organization or not cls._schema_ready():
            return payload

        referral_query = AffiliateReferral.query.filter_by(
            referrer_organization_id=organization.id
        )
        pagination = referral_query.order_by(AffiliateReferral.signed_up_at.desc()).paginate(
            page=max(1, int(page)),
            per_page=max(1, min(int(per_page), 50)),
            error_out=False,
        )

        active_referred = (
            db.session.query(func.count(AffiliateReferral.id))
            .join(
                Organization,
                AffiliateReferral.referred_organization_id == Organization.id,
            )
            .filter(
                AffiliateReferral.referrer_organization_id == organization.id,
                Organization.is_active.is_(True),
            )
            .scalar()
            or 0
        )
        total_commission_cents = (
            db.session.query(func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0))
            .filter(AffiliateMonthlyEarning.referrer_organization_id == organization.id)
            .scalar()
            or 0
        )

        by_user_rows = (
            db.session.query(
                User.id.label("user_id"),
                User.first_name.label("first_name"),
                User.last_name.label("last_name"),
                func.count(func.distinct(AffiliateReferral.id)).label("referral_count"),
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).label(
                    "commission_cents"
                ),
            )
            .filter(User.organization_id == organization.id, User.user_type == "customer")
            .outerjoin(AffiliateReferral, AffiliateReferral.referrer_user_id == User.id)
            .outerjoin(
                AffiliateMonthlyEarning,
                AffiliateMonthlyEarning.affiliate_referral_id == AffiliateReferral.id,
            )
            .group_by(User.id, User.first_name, User.last_name)
            .order_by(
                func.count(func.distinct(AffiliateReferral.id)).desc(),
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).desc(),
            )
            .all()
        )

        referral_rows = []
        for referral in pagination.items:
            referred_org = referral.referred_organization
            referrer_user = referral.referrer_user
            referral_rows.append(
                {
                    "referrer_user_id": referral.referrer_user_id,
                    "referrer_name": (
                        f"{(getattr(referrer_user, 'first_name', '') or '').strip()} {(getattr(referrer_user, 'last_name', '') or '').strip()}".strip()
                        or getattr(referrer_user, "username", f"User {referral.referrer_user_id}")
                    ),
                    "first_name_redacted": cls._redacted_first_name(referred_org),
                    "signed_up_at": referral.signed_up_at,
                    "referral_code": referral.referral_code,
                }
            )

        payload.update(
            {
                "enabled": True,
                "total_referrals": pagination.total,
                "active_referred_organizations": int(active_referred),
                "total_commission_cents": int(total_commission_cents),
                "total_commission_display": cls._format_currency_cents(total_commission_cents),
                "commission_percentage": float(
                    getattr(organization.tier, "commission_percentage", 0) or 0
                ),
                "by_user_rows": [
                    {
                        "user_id": row.user_id,
                        "user_name": (
                            f"{(row.first_name or '').strip()} {(row.last_name or '').strip()}".strip()
                            or f"User {row.user_id}"
                        ),
                        "referral_count": int(row.referral_count or 0),
                        "commission_cents": int(row.commission_cents or 0),
                        "commission_display": cls._format_currency_cents(
                            row.commission_cents or 0
                        ),
                    }
                    for row in by_user_rows
                ],
                "referrals": referral_rows,
                "page": pagination.page,
                "pages": max(1, pagination.pages),
                "has_prev": pagination.has_prev,
                "has_next": pagination.has_next,
            }
        )
        return payload

    @classmethod
    def build_developer_ecosystem_context(
        cls, *, page: int = 1, per_page: int = 25
    ) -> dict[str, Any]:
        payload = {
            "enabled": False,
            "total_referrals": 0,
            "total_paid_out_cents": 0,
            "total_paid_out_display": "$0.00",
            "total_accrued_cents": 0,
            "total_accrued_display": "$0.00",
            "organization_rows": [],
            "page": page,
            "pages": 1,
            "has_prev": False,
            "has_next": False,
            "total_organizations": 0,
        }
        if not cls._schema_ready():
            return payload

        page = max(1, int(page))
        per_page = max(1, min(int(per_page), 100))
        offset = (page - 1) * per_page

        grouped_query = (
            db.session.query(
                Organization.id.label("organization_id"),
                Organization.name.label("organization_name"),
                func.count(func.distinct(AffiliateReferral.id)).label("referral_count"),
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).label(
                    "commission_cents"
                ),
            )
            .join(
                AffiliateReferral,
                AffiliateReferral.referrer_organization_id == Organization.id,
            )
            .outerjoin(
                AffiliateMonthlyEarning,
                AffiliateMonthlyEarning.affiliate_referral_id == AffiliateReferral.id,
            )
            .group_by(Organization.id, Organization.name)
            .order_by(
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).desc(),
                func.count(func.distinct(AffiliateReferral.id)).desc(),
            )
        )

        total_organizations = grouped_query.count()
        rows = grouped_query.limit(per_page).offset(offset).all()
        pages = max(1, (total_organizations + per_page - 1) // per_page)

        total_referrals = AffiliateReferral.query.count()
        total_paid_out_cents = (
            db.session.query(func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0))
            .filter(AffiliateMonthlyEarning.payout_status == "paid")
            .scalar()
            or 0
        )
        total_accrued_cents = (
            db.session.query(func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0))
            .filter(AffiliateMonthlyEarning.payout_status != "paid")
            .scalar()
            or 0
        )

        payload.update(
            {
                "enabled": True,
                "total_referrals": int(total_referrals),
                "total_paid_out_cents": int(total_paid_out_cents),
                "total_paid_out_display": cls._format_currency_cents(total_paid_out_cents),
                "total_accrued_cents": int(total_accrued_cents),
                "total_accrued_display": cls._format_currency_cents(total_accrued_cents),
                "organization_rows": [
                    {
                        "organization_id": row.organization_id,
                        "organization_name": row.organization_name,
                        "referral_count": int(row.referral_count or 0),
                        "commission_cents": int(row.commission_cents or 0),
                        "commission_display": cls._format_currency_cents(
                            row.commission_cents or 0
                        ),
                    }
                    for row in rows
                ],
                "page": page,
                "pages": pages,
                "has_prev": page > 1,
                "has_next": page < pages,
                "total_organizations": int(total_organizations),
            }
        )
        return payload

    @classmethod
    def get_or_create_payout_account(
        cls, organization: Organization | None
    ) -> AffiliatePayoutAccount | None:
        if not organization or not cls._schema_ready():
            return None
        payout_account = AffiliatePayoutAccount.query.filter_by(
            organization_id=organization.id
        ).first()
        if payout_account:
            return payout_account
        payout_account = AffiliatePayoutAccount(
            organization_id=organization.id,
            payout_provider="stripe",
            created_at=TimezoneUtils.utc_now(),
            updated_at=TimezoneUtils.utc_now(),
        )
        db.session.add(payout_account)
        db.session.commit()
        return payout_account
