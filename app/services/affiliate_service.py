"""Affiliate program service helpers.

Synopsis:
Centralizes affiliate link generation, referral attribution, and dashboard
summary payloads for settings, organization, and developer surfaces.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, timedelta
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
        billing_mode_snapshot: str | None = None,
        billing_cycle_snapshot: str | None = None,
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
            billing_mode_snapshot=(billing_mode_snapshot or "").strip() or None,
            billing_cycle_snapshot=(billing_cycle_snapshot or "").strip() or None,
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

    @classmethod
    def mark_referral_churned_for_organization(
        cls,
        referred_organization_id: int | None,
        *,
        churned_at=None,
        auto_commit: bool = False,
    ) -> bool:
        if not referred_organization_id or not cls._schema_ready():
            return False
        referral = AffiliateReferral.query.filter_by(
            referred_organization_id=referred_organization_id
        ).first()
        if not referral:
            return False
        if referral.churned_at is not None:
            return False
        referral.churned_at = churned_at or TimezoneUtils.utc_now()
        if auto_commit:
            db.session.commit()
        return True

    @classmethod
    def clear_referral_churn_for_organization(
        cls, referred_organization_id: int | None, *, auto_commit: bool = False
    ) -> bool:
        if not referred_organization_id or not cls._schema_ready():
            return False
        referral = AffiliateReferral.query.filter_by(
            referred_organization_id=referred_organization_id
        ).first()
        if not referral or referral.churned_at is None:
            return False
        referral.churned_at = None
        if auto_commit:
            db.session.commit()
        return True

    @staticmethod
    def _status_is_canceled(org: Organization | None) -> bool:
        if not org:
            return False
        billing_status = str(getattr(org, "billing_status", "") or "").lower()
        subscription_status = str(getattr(org, "subscription_status", "") or "").lower()
        return billing_status in {"canceled", "cancelled", "suspended"} or subscription_status in {
            "canceled",
            "cancelled",
            "suspended",
        }

    @classmethod
    def _compute_referral_type(cls, referral: AffiliateReferral) -> str:
        mode = (referral.billing_mode_snapshot or "").strip().lower()
        cycle = (referral.billing_cycle_snapshot or "").strip().lower()
        if mode == "lifetime" or cycle == "lifetime":
            return "lifetime"
        if cycle in {"monthly", "yearly"}:
            return cycle
        if mode == "standard":
            return "monthly"
        return "special_offer"

    @classmethod
    def build_organization_analytics_context(
        cls, organization: Organization | None
    ) -> dict[str, Any]:
        now = TimezoneUtils.utc_now()
        payload = {
            "enabled": False,
            "total_referrals": 0,
            "active_referrals": 0,
            "churn_rate_percent": 0.0,
            "members_left_this_month": 0,
            "average_lifespan_days": 0.0,
            "average_days_to_churn": 0.0,
            "commission_percentage": 0.0,
            "current_month_income_cents": 0,
            "current_month_income_display": "$0.00",
            "monthly_income_12m": {"labels": [], "values": []},
            "referrals_trend": {
                "day": {"labels": [], "values": []},
                "week": {"labels": [], "values": []},
                "month": {"labels": [], "values": []},
            },
            "tier_spread": {"labels": [], "values": []},
            "subscription_type_spread": {"labels": [], "values": []},
        }
        if not organization or not cls._schema_ready():
            return payload

        referrals = AffiliateReferral.query.filter_by(
            referrer_organization_id=organization.id
        ).all()
        total_referrals = len(referrals)

        tier_counts: dict[str, int] = {}
        subscription_type_counts: dict[str, int] = {}
        day_counts: dict[str, int] = {}
        week_counts: dict[str, int] = {}
        month_counts: dict[str, int] = {}

        churned_count = 0
        churn_durations: list[float] = []
        lifespan_durations: list[float] = []
        current_month_churns = 0

        month_start = date(now.year, now.month, 1)
        for referral in referrals:
            signed_up_at = referral.signed_up_at or now
            referred_org = referral.referred_organization
            tier_name = (
                referred_org.tier.name
                if referred_org and getattr(referred_org, "tier", None)
                else "Unknown Tier"
            )
            tier_counts[tier_name] = tier_counts.get(tier_name, 0) + 1

            referral_type = cls._compute_referral_type(referral)
            subscription_type_counts[referral_type] = (
                subscription_type_counts.get(referral_type, 0) + 1
            )

            day_key = signed_up_at.date().isoformat()
            iso_year, iso_week, _ = signed_up_at.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            month_key = f"{signed_up_at.year}-{signed_up_at.month:02d}"
            day_counts[day_key] = day_counts.get(day_key, 0) + 1
            week_counts[week_key] = week_counts.get(week_key, 0) + 1
            month_counts[month_key] = month_counts.get(month_key, 0) + 1

            churned_at = referral.churned_at
            status_indicates_churn = cls._status_is_canceled(referred_org)
            is_churned = churned_at is not None or status_indicates_churn
            end_for_lifespan = churned_at or now
            lifespan_days = max(0.0, (end_for_lifespan - signed_up_at).total_seconds() / 86400.0)
            lifespan_durations.append(lifespan_days)

            if is_churned:
                churned_count += 1
                if churned_at is not None:
                    churn_days = max(
                        0.0, (churned_at - signed_up_at).total_seconds() / 86400.0
                    )
                    churn_durations.append(churn_days)
                if churned_at is not None and churned_at.date() >= month_start:
                    current_month_churns += 1

        # Time-series buckets
        day_labels = []
        day_values = []
        for index in range(29, -1, -1):
            bucket_date = (now - timedelta(days=index)).date()
            key = bucket_date.isoformat()
            day_labels.append(bucket_date.strftime("%m-%d"))
            day_values.append(day_counts.get(key, 0))

        week_labels = []
        week_values = []
        for index in range(11, -1, -1):
            bucket_date = now.date() - timedelta(days=index * 7)
            iso_year, iso_week, _ = bucket_date.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            week_labels.append(key)
            week_values.append(week_counts.get(key, 0))

        month_labels = []
        month_values = []
        for index in range(11, -1, -1):
            pointer = now.date().replace(day=1)
            for _ in range(index):
                prev = pointer - timedelta(days=1)
                pointer = prev.replace(day=1)
            key = f"{pointer.year}-{pointer.month:02d}"
            month_labels.append(pointer.strftime("%b %Y"))
            month_values.append(month_counts.get(key, 0))

        # Income 12 months
        earning_rows = (
            db.session.query(
                AffiliateMonthlyEarning.earning_month,
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).label(
                    "commission_cents"
                ),
            )
            .filter(AffiliateMonthlyEarning.referrer_organization_id == organization.id)
            .group_by(AffiliateMonthlyEarning.earning_month)
            .all()
        )
        earnings_map = {
            row.earning_month.strftime("%Y-%m"): int(row.commission_cents or 0)
            for row in earning_rows
            if row.earning_month
        }
        income_labels = []
        income_values = []
        current_month = now.date().replace(day=1)
        for index in range(11, -1, -1):
            pointer = current_month
            for _ in range(index):
                prev = pointer - timedelta(days=1)
                pointer = prev.replace(day=1)
            map_key = pointer.strftime("%Y-%m")
            income_labels.append(pointer.strftime("%b %Y"))
            income_values.append(earnings_map.get(map_key, 0))

        current_month_income_cents = earnings_map.get(now.strftime("%Y-%m"), 0)
        active_referrals = max(0, total_referrals - churned_count)
        churn_rate = (churned_count / total_referrals * 100.0) if total_referrals else 0.0
        avg_lifespan = (
            sum(lifespan_durations) / len(lifespan_durations) if lifespan_durations else 0.0
        )
        avg_to_churn = (
            sum(churn_durations) / len(churn_durations) if churn_durations else 0.0
        )

        payload.update(
            {
                "enabled": True,
                "total_referrals": total_referrals,
                "active_referrals": active_referrals,
                "churn_rate_percent": round(churn_rate, 2),
                "members_left_this_month": int(current_month_churns),
                "average_lifespan_days": round(avg_lifespan, 2),
                "average_days_to_churn": round(avg_to_churn, 2),
                "commission_percentage": float(
                    getattr(organization.tier, "commission_percentage", 0) or 0
                ),
                "current_month_income_cents": int(current_month_income_cents),
                "current_month_income_display": cls._format_currency_cents(
                    current_month_income_cents
                ),
                "monthly_income_12m": {"labels": income_labels, "values": income_values},
                "referrals_trend": {
                    "day": {"labels": day_labels, "values": day_values},
                    "week": {"labels": week_labels, "values": week_values},
                    "month": {"labels": month_labels, "values": month_values},
                },
                "tier_spread": {
                    "labels": list(tier_counts.keys()),
                    "values": [tier_counts[label] for label in tier_counts.keys()],
                },
                "subscription_type_spread": {
                    "labels": list(subscription_type_counts.keys()),
                    "values": [
                        subscription_type_counts[label]
                        for label in subscription_type_counts.keys()
                    ],
                },
            }
        )
        return payload
