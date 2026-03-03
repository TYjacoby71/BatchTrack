"""Affiliate program service helpers.

Synopsis:
Centralizes affiliate link generation, referral attribution, and dashboard
summary payloads for settings, organization, and developer surfaces.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, func, inspect

from ..extensions import db
from ..models import Organization, User
from ..models.affiliate import (
    AffiliateMonthlyEarning,
    AffiliatePayoutAccount,
    AffiliateProfile,
    AffiliateReferral,
)
from .affiliate import (
    AffiliatePayoutNotificationService,
    PAYOUT_STATUS_COMPLETE,
    PAYOUT_STATUS_PENDING,
    PAYOUT_STATUS_SENT,
    PAYOUT_STATUS_UNSUCCESSFUL,
    normalize_payout_status,
    payout_status_label,
    payout_status_query_values,
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
            "payout_status_summary": cls._empty_payout_status_summary(),
            "recent_payout_batches": [],
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
        payout_filters = [AffiliateMonthlyEarning.referrer_user_id == user.id]
        payout_status_summary = cls._build_payout_status_summary(payout_filters)
        recent_payout_batches = cls._build_recent_payout_batches(
            payout_filters, limit=6
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
            "payout_status_summary": payout_status_summary,
            "recent_payout_batches": recent_payout_batches,
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
            "payout_status_summary": cls._empty_payout_status_summary(),
            "recent_payout_batches": [],
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
        payout_filters = [
            AffiliateMonthlyEarning.referrer_organization_id == organization.id
        ]
        payout_status_summary = cls._build_payout_status_summary(payout_filters)
        recent_payout_batches = cls._build_recent_payout_batches(
            payout_filters, limit=8
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
                "payout_status_summary": payout_status_summary,
                "recent_payout_batches": recent_payout_batches,
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
            "total_pending_cents": 0,
            "total_pending_display": "$0.00",
            "total_sent_cents": 0,
            "total_sent_display": "$0.00",
            "total_complete_cents": 0,
            "total_complete_display": "$0.00",
            "total_unsuccessful_cents": 0,
            "total_unsuccessful_display": "$0.00",
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
        payout_summary = cls._build_payout_status_summary([])
        total_pending_cents = int(
            payout_summary[PAYOUT_STATUS_PENDING]["commission_cents"] or 0
        )
        total_sent_cents = int(payout_summary[PAYOUT_STATUS_SENT]["commission_cents"] or 0)
        total_complete_cents = int(
            payout_summary[PAYOUT_STATUS_COMPLETE]["commission_cents"] or 0
        )
        total_unsuccessful_cents = int(
            payout_summary[PAYOUT_STATUS_UNSUCCESSFUL]["commission_cents"] or 0
        )
        total_accrued_cents = (
            total_pending_cents + total_sent_cents + total_unsuccessful_cents
        )
        total_paid_out_cents = total_complete_cents

        payload.update(
            {
                "enabled": True,
                "total_referrals": int(total_referrals),
                "total_paid_out_cents": int(total_paid_out_cents),
                "total_paid_out_display": cls._format_currency_cents(total_paid_out_cents),
                "total_accrued_cents": int(total_accrued_cents),
                "total_accrued_display": cls._format_currency_cents(total_accrued_cents),
                "total_pending_cents": total_pending_cents,
                "total_pending_display": cls._format_currency_cents(total_pending_cents),
                "total_sent_cents": total_sent_cents,
                "total_sent_display": cls._format_currency_cents(total_sent_cents),
                "total_complete_cents": total_complete_cents,
                "total_complete_display": cls._format_currency_cents(total_complete_cents),
                "total_unsuccessful_cents": total_unsuccessful_cents,
                "total_unsuccessful_display": cls._format_currency_cents(
                    total_unsuccessful_cents
                ),
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

    @staticmethod
    def _parse_earning_month(earning_month_value: str | date | None) -> date | None:
        if isinstance(earning_month_value, date):
            return earning_month_value
        raw_value = str(earning_month_value or "").strip()
        if not raw_value:
            return None
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d").date()
        except ValueError:
            return None

    @staticmethod
    def _payout_status_case_expression():
        """Normalize legacy payout statuses directly in SQL queries."""
        return case(
            (
                AffiliateMonthlyEarning.payout_status.in_(
                    payout_status_query_values(PAYOUT_STATUS_COMPLETE)
                ),
                PAYOUT_STATUS_COMPLETE,
            ),
            (
                AffiliateMonthlyEarning.payout_status.in_(
                    payout_status_query_values(PAYOUT_STATUS_SENT)
                ),
                PAYOUT_STATUS_SENT,
            ),
            (
                AffiliateMonthlyEarning.payout_status.in_(
                    payout_status_query_values(PAYOUT_STATUS_UNSUCCESSFUL)
                ),
                PAYOUT_STATUS_UNSUCCESSFUL,
            ),
            else_=PAYOUT_STATUS_PENDING,
        )

    @classmethod
    def _empty_payout_status_summary(cls) -> dict[str, dict[str, Any]]:
        """Return the shared payout status dictionary contract."""
        return {
            status: {
                "status": status,
                "label": payout_status_label(status),
                "count": 0,
                "commission_cents": 0,
                "commission_display": "$0.00",
            }
            for status in (
                PAYOUT_STATUS_PENDING,
                PAYOUT_STATUS_SENT,
                PAYOUT_STATUS_COMPLETE,
                PAYOUT_STATUS_UNSUCCESSFUL,
            )
        }

    @classmethod
    def _build_payout_status_summary(cls, filters: list[Any]) -> dict[str, dict[str, Any]]:
        """Aggregate payout counts/totals by canonical status."""
        status_alias = cls._payout_status_case_expression().label("canonical_status")
        grouped_rows = (
            db.session.query(
                status_alias,
                func.count(AffiliateMonthlyEarning.id).label("count_rows"),
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).label(
                    "commission_cents"
                ),
            )
            .filter(*filters)
            .group_by(status_alias)
            .all()
        )
        summary = cls._empty_payout_status_summary()
        for row in grouped_rows:
            canonical = normalize_payout_status(getattr(row, "canonical_status", None))
            if not canonical:
                canonical = PAYOUT_STATUS_PENDING
            commission_cents = int(getattr(row, "commission_cents", 0) or 0)
            summary[canonical]["count"] = int(getattr(row, "count_rows", 0) or 0)
            summary[canonical]["commission_cents"] = commission_cents
            summary[canonical]["commission_display"] = cls._format_currency_cents(
                commission_cents
            )
        return summary

    @classmethod
    def _build_recent_payout_batches(
        cls,
        filters: list[Any],
        *,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        """Build recent org/user payout batches for status visibility cards."""
        status_alias = cls._payout_status_case_expression().label("canonical_status")
        rows = (
            db.session.query(
                AffiliateMonthlyEarning.earning_month.label("earning_month"),
                status_alias,
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).label(
                    "commission_cents"
                ),
                func.max(AffiliateMonthlyEarning.payout_reference).label("payout_reference"),
            )
            .filter(*filters)
            .group_by(AffiliateMonthlyEarning.earning_month, status_alias)
            .order_by(AffiliateMonthlyEarning.earning_month.desc())
            .limit(max(1, int(limit)))
            .all()
        )
        return [
            {
                "earning_month": row.earning_month,
                "earning_month_iso": row.earning_month.isoformat() if row.earning_month else "",
                "earning_month_display": (
                    row.earning_month.strftime("%b %Y") if row.earning_month else "Unknown"
                ),
                "payout_status": normalize_payout_status(getattr(row, "canonical_status", None))
                or PAYOUT_STATUS_PENDING,
                "payout_status_label": payout_status_label(
                    getattr(row, "canonical_status", None)
                ),
                "commission_cents": int(getattr(row, "commission_cents", 0) or 0),
                "commission_display": cls._format_currency_cents(
                    getattr(row, "commission_cents", 0) or 0
                ),
                "payout_reference": row.payout_reference,
            }
            for row in rows
        ]

    @staticmethod
    def _to_utc_aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def build_developer_payout_operations_context(
        cls,
        *,
        page: int = 1,
        per_page: int = 25,
        status_filter: str = PAYOUT_STATUS_PENDING,
        organization_query: str | None = None,
        organization_id: int | None = None,
    ) -> dict[str, Any]:
        payload = {
            "enabled": False,
            "rows": [],
            "page": page,
            "pages": 1,
            "has_prev": False,
            "has_next": False,
            "total_batches": 0,
            "outstanding_payout_batches": 0,
            "pending_payout_batches": 0,
            "sent_payout_batches": 0,
            "unsuccessful_payout_batches": 0,
            "paid_payout_batches": 0,
            "total_paid_out_cents": 0,
            "total_paid_out_display": "$0.00",
            "total_accrued_cents": 0,
            "total_accrued_display": "$0.00",
            "total_pending_cents": 0,
            "total_pending_display": "$0.00",
            "total_sent_cents": 0,
            "total_sent_display": "$0.00",
            "total_complete_cents": 0,
            "total_complete_display": "$0.00",
            "total_unsuccessful_cents": 0,
            "total_unsuccessful_display": "$0.00",
            "payout_status_summary": cls._empty_payout_status_summary(),
            "status_filter": PAYOUT_STATUS_PENDING,
            "status_options": [
                {"value": PAYOUT_STATUS_PENDING, "label": payout_status_label(PAYOUT_STATUS_PENDING)},
                {"value": PAYOUT_STATUS_SENT, "label": payout_status_label(PAYOUT_STATUS_SENT)},
                {"value": PAYOUT_STATUS_COMPLETE, "label": payout_status_label(PAYOUT_STATUS_COMPLETE)},
                {
                    "value": PAYOUT_STATUS_UNSUCCESSFUL,
                    "label": payout_status_label(PAYOUT_STATUS_UNSUCCESSFUL),
                },
                {"value": "all", "label": "All"},
            ],
            "organization_query": (organization_query or "").strip(),
            "organization_id": int(organization_id) if organization_id else None,
        }
        if not cls._schema_ready():
            return payload

        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 25), 100))
        requested_status_filter = (status_filter or PAYOUT_STATUS_PENDING).strip().lower()
        if requested_status_filter == "all":
            status_filter = "all"
        else:
            status_filter = (
                normalize_payout_status(requested_status_filter) or PAYOUT_STATUS_PENDING
            )
        payload["status_filter"] = status_filter
        payload["organization_query"] = (organization_query or "").strip()

        canonical_status_expr = cls._payout_status_case_expression()
        sum_gross_expr = func.coalesce(func.sum(AffiliateMonthlyEarning.gross_revenue_cents), 0)
        sum_commission_expr = func.coalesce(
            func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0
        )
        grouped_query = (
            db.session.query(
                AffiliateMonthlyEarning.referrer_organization_id.label("organization_id"),
                Organization.name.label("organization_name"),
                AffiliateMonthlyEarning.earning_month.label("earning_month"),
                AffiliateMonthlyEarning.currency.label("currency"),
                canonical_status_expr.label("canonical_payout_status"),
                func.count(AffiliateMonthlyEarning.id).label("earning_rows"),
                func.count(
                    func.distinct(AffiliateMonthlyEarning.affiliate_referral_id)
                ).label("referral_count"),
                sum_gross_expr.label("gross_cents"),
                sum_commission_expr.label("commission_cents"),
                func.max(AffiliateMonthlyEarning.payout_reference).label("payout_reference"),
            )
            .join(
                Organization,
                Organization.id == AffiliateMonthlyEarning.referrer_organization_id,
            )
        )
        if organization_id:
            grouped_query = grouped_query.filter(
                AffiliateMonthlyEarning.referrer_organization_id == int(organization_id)
            )
            payload["organization_id"] = int(organization_id)
        if organization_query:
            grouped_query = grouped_query.filter(
                func.lower(Organization.name).like(
                    f"%{str(organization_query).strip().lower()}%"
                )
            )
        grouped_query = grouped_query.group_by(
            AffiliateMonthlyEarning.referrer_organization_id,
            Organization.name,
            AffiliateMonthlyEarning.earning_month,
            AffiliateMonthlyEarning.currency,
            canonical_status_expr,
        ).order_by(AffiliateMonthlyEarning.earning_month.desc(), sum_commission_expr.desc())

        summary_rows = grouped_query.all()
        payout_status_summary = cls._empty_payout_status_summary()
        for row in summary_rows:
            canonical_status = normalize_payout_status(
                getattr(row, "canonical_payout_status", None)
            )
            if not canonical_status:
                canonical_status = PAYOUT_STATUS_PENDING
            payout_status_summary[canonical_status]["count"] += 1
            payout_status_summary[canonical_status]["commission_cents"] += int(
                row.commission_cents or 0
            )
        for status_key in payout_status_summary:
            payout_status_summary[status_key]["commission_display"] = cls._format_currency_cents(
                payout_status_summary[status_key]["commission_cents"]
            )

        filtered_query = grouped_query
        if status_filter != "all":
            filtered_query = filtered_query.filter(
                AffiliateMonthlyEarning.payout_status.in_(
                    payout_status_query_values(status_filter)
                )
            )

        total_batches = filtered_query.count()
        offset = (page - 1) * per_page
        rows = filtered_query.limit(per_page).offset(offset).all()
        pages = max(1, (total_batches + per_page - 1) // per_page)

        total_pending_cents = int(
            payout_status_summary[PAYOUT_STATUS_PENDING]["commission_cents"] or 0
        )
        total_sent_cents = int(
            payout_status_summary[PAYOUT_STATUS_SENT]["commission_cents"] or 0
        )
        total_complete_cents = int(
            payout_status_summary[PAYOUT_STATUS_COMPLETE]["commission_cents"] or 0
        )
        total_unsuccessful_cents = int(
            payout_status_summary[PAYOUT_STATUS_UNSUCCESSFUL]["commission_cents"] or 0
        )
        total_accrued_cents = (
            total_pending_cents + total_sent_cents + total_unsuccessful_cents
        )
        total_paid_out_cents = total_complete_cents
        pending_payout_batches = int(
            payout_status_summary[PAYOUT_STATUS_PENDING]["count"] or 0
        )
        sent_payout_batches = int(
            payout_status_summary[PAYOUT_STATUS_SENT]["count"] or 0
        )
        unsuccessful_payout_batches = int(
            payout_status_summary[PAYOUT_STATUS_UNSUCCESSFUL]["count"] or 0
        )
        paid_payout_batches = int(
            payout_status_summary[PAYOUT_STATUS_COMPLETE]["count"] or 0
        )
        outstanding_payout_batches = (
            pending_payout_batches + sent_payout_batches + unsuccessful_payout_batches
        )

        payload.update(
            {
                "enabled": True,
                "rows": [
                    {
                        "organization_id": row.organization_id,
                        "organization_name": row.organization_name,
                        "earning_month": row.earning_month,
                        "earning_month_iso": (
                            row.earning_month.isoformat() if row.earning_month else ""
                        ),
                        "earning_month_display": (
                            row.earning_month.strftime("%b %Y")
                            if row.earning_month
                            else "Unknown"
                        ),
                        "currency": (row.currency or "usd").upper(),
                        "payout_status": normalize_payout_status(
                            getattr(row, "canonical_payout_status", None)
                        )
                        or PAYOUT_STATUS_PENDING,
                        "payout_status_label": payout_status_label(
                            getattr(row, "canonical_payout_status", None)
                        ),
                        "earning_rows": int(row.earning_rows or 0),
                        "referral_count": int(row.referral_count or 0),
                        "gross_cents": int(row.gross_cents or 0),
                        "gross_display": cls._format_currency_cents(row.gross_cents or 0),
                        "commission_cents": int(row.commission_cents or 0),
                        "commission_display": cls._format_currency_cents(
                            row.commission_cents or 0
                        ),
                        "effective_rate_percent": (
                            round(
                                (
                                    (int(row.commission_cents or 0))
                                    / max(1, int(row.gross_cents or 0))
                                )
                                * 100.0,
                                2,
                            )
                            if int(row.gross_cents or 0) > 0
                            else 0.0
                        ),
                        "payout_reference": row.payout_reference,
                    }
                    for row in rows
                ],
                "page": page,
                "pages": pages,
                "has_prev": page > 1,
                "has_next": page < pages,
                "total_batches": int(total_batches),
                "outstanding_payout_batches": int(outstanding_payout_batches),
                "pending_payout_batches": int(pending_payout_batches),
                "sent_payout_batches": int(sent_payout_batches),
                "unsuccessful_payout_batches": int(unsuccessful_payout_batches),
                "paid_payout_batches": int(paid_payout_batches),
                "total_paid_out_cents": int(total_paid_out_cents),
                "total_paid_out_display": cls._format_currency_cents(total_paid_out_cents),
                "total_accrued_cents": int(total_accrued_cents),
                "total_accrued_display": cls._format_currency_cents(total_accrued_cents),
                "total_pending_cents": int(total_pending_cents),
                "total_pending_display": cls._format_currency_cents(total_pending_cents),
                "total_sent_cents": int(total_sent_cents),
                "total_sent_display": cls._format_currency_cents(total_sent_cents),
                "total_complete_cents": int(total_complete_cents),
                "total_complete_display": cls._format_currency_cents(total_complete_cents),
                "total_unsuccessful_cents": int(total_unsuccessful_cents),
                "total_unsuccessful_display": cls._format_currency_cents(
                    total_unsuccessful_cents
                ),
                "payout_status_summary": payout_status_summary,
            }
        )
        return payload

    @classmethod
    def update_monthly_earnings_status(
        cls,
        *,
        organization_id: int | None,
        earning_month: str | date | None,
        target_status: str | None,
        payout_reference: str | None = None,
        auto_commit: bool = True,
    ) -> dict[str, Any]:
        if not cls._schema_ready():
            return {"ok": False, "reason": "schema_not_ready", "updated_rows": 0}
        canonical_target_status = normalize_payout_status(target_status)
        if not canonical_target_status:
            return {"ok": False, "reason": "invalid_status", "updated_rows": 0}
        month_date = cls._parse_earning_month(earning_month)
        if not organization_id or not month_date:
            return {"ok": False, "reason": "invalid_input", "updated_rows": 0}

        rows = AffiliateMonthlyEarning.query.filter_by(
            referrer_organization_id=int(organization_id),
            earning_month=month_date,
        ).all()
        if not rows:
            return {"ok": False, "reason": "not_found", "updated_rows": 0}

        now = TimezoneUtils.utc_now()
        updated_rows = 0
        status_changed_rows = 0
        status_changed_commission_cents = 0
        changed_referrer_user_ids: set[int] = set()
        clean_reference = (payout_reference or "").strip() or None
        for row in rows:
            changed = False
            current_status = normalize_payout_status(row.payout_status) or PAYOUT_STATUS_PENDING
            if current_status != canonical_target_status:
                row.payout_status = canonical_target_status
                status_changed_rows += 1
                status_changed_commission_cents += int(row.commission_amount_cents or 0)
                changed = True
            should_store_reference = canonical_target_status in {
                PAYOUT_STATUS_SENT,
                PAYOUT_STATUS_COMPLETE,
            }
            if should_store_reference:
                if clean_reference and row.payout_reference != clean_reference:
                    row.payout_reference = clean_reference
                    changed = True
            elif row.payout_reference:
                row.payout_reference = None
                changed = True

            if changed:
                row.updated_at = now
                updated_rows += 1
                if row.referrer_user_id:
                    changed_referrer_user_ids.add(int(row.referrer_user_id))

        if updated_rows > 0 and auto_commit:
            db.session.commit()
        return {
            "ok": True,
            "reason": None,
            "updated_rows": int(updated_rows),
            "status_changed_rows": int(status_changed_rows),
            "status_changed_commission_cents": int(status_changed_commission_cents),
            "organization_id": int(organization_id),
            "earning_month": month_date.isoformat(),
            "earning_month_date": month_date,
            "target_status": canonical_target_status,
            "target_status_label": payout_status_label(canonical_target_status),
            "referrer_user_ids": sorted(changed_referrer_user_ids),
        }

    @classmethod
    def mark_monthly_earnings_paid(
        cls,
        *,
        organization_id: int | None,
        earning_month: str | date | None,
        payout_reference: str | None = None,
        auto_commit: bool = True,
    ) -> dict[str, Any]:
        """Backward-compatible helper that maps paid -> complete."""
        return cls.update_monthly_earnings_status(
            organization_id=organization_id,
            earning_month=earning_month,
            target_status=PAYOUT_STATUS_COMPLETE,
            payout_reference=payout_reference,
            auto_commit=auto_commit,
        )

    @classmethod
    def mark_monthly_earnings_accrued(
        cls,
        *,
        organization_id: int | None,
        earning_month: str | date | None,
        auto_commit: bool = True,
    ) -> dict[str, Any]:
        """Backward-compatible helper that maps accrued -> pending."""
        return cls.update_monthly_earnings_status(
            organization_id=organization_id,
            earning_month=earning_month,
            target_status=PAYOUT_STATUS_PENDING,
            auto_commit=auto_commit,
        )

    @classmethod
    def notify_payout_status_update(
        cls,
        *,
        organization_id: int | None,
        earning_month: date | None,
        payout_status: str | None,
        commission_amount_cents: int,
        updated_rows: int,
        payout_reference: str | None = None,
        referrer_user_ids: list[int] | None = None,
    ) -> dict[str, int]:
        """Send payout status update email notifications to org recipients."""
        if not organization_id:
            return {"attempted": 0, "sent": 0}
        organization = Organization.query.get(int(organization_id))
        if not organization:
            return {"attempted": 0, "sent": 0}
        return AffiliatePayoutNotificationService.send_payout_status_update_email(
            organization=organization,
            earning_month=earning_month,
            payout_status=payout_status or PAYOUT_STATUS_PENDING,
            commission_amount_cents=int(commission_amount_cents or 0),
            updated_rows=int(updated_rows or 0),
            payout_reference=payout_reference,
            referrer_user_ids=referrer_user_ids or [],
        )

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
            "effective_commission_rate_percent": 0.0,
            "current_month_income_cents": 0,
            "current_month_income_display": "$0.00",
            "current_month_gross_cents": 0,
            "current_month_gross_display": "$0.00",
            "monthly_income_12m": {"labels": [], "values": []},
            "monthly_commission_rate_12m": {"labels": [], "values": []},
            "referrals_trend": {
                "day": {"labels": [], "values": []},
                "week": {"labels": [], "values": []},
                "month": {"labels": [], "values": []},
            },
            "tier_spread": {"labels": [], "values": []},
            "subscription_type_spread": {"labels": [], "values": []},
            "retention_windows": [],
            "lifespan_buckets": {"labels": [], "values": []},
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
        retention_windows_days = (30, 90, 180)
        retention_trackers = {
            window_days: {"eligible": 0, "retained": 0}
            for window_days in retention_windows_days
        }
        lifespan_bucket_counts = {
            "<30 days": 0,
            "30-89 days": 0,
            "90-179 days": 0,
            "180+ days": 0,
        }

        month_start = date(now.year, now.month, 1)
        for referral in referrals:
            signed_up_at = cls._to_utc_aware(referral.signed_up_at) or now
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

            churned_at = cls._to_utc_aware(referral.churned_at)
            status_indicates_churn = cls._status_is_canceled(referred_org)
            is_churned = churned_at is not None or status_indicates_churn
            end_for_lifespan = churned_at or now
            lifespan_days = max(0.0, (end_for_lifespan - signed_up_at).total_seconds() / 86400.0)
            lifespan_durations.append(lifespan_days)
            referral_age_days = max(0.0, (now - signed_up_at).total_seconds() / 86400.0)

            if lifespan_days < 30:
                lifespan_bucket_counts["<30 days"] += 1
            elif lifespan_days < 90:
                lifespan_bucket_counts["30-89 days"] += 1
            elif lifespan_days < 180:
                lifespan_bucket_counts["90-179 days"] += 1
            else:
                lifespan_bucket_counts["180+ days"] += 1

            churn_days = None
            if churned_at is not None:
                churn_days = max(0.0, (churned_at - signed_up_at).total_seconds() / 86400.0)

            for window_days in retention_windows_days:
                if referral_age_days < window_days:
                    continue
                retention_trackers[window_days]["eligible"] += 1
                if (not is_churned) or (
                    churn_days is not None and churn_days >= float(window_days)
                ):
                    retention_trackers[window_days]["retained"] += 1

            if is_churned:
                churned_count += 1
                if churn_days is not None:
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
                func.coalesce(func.sum(AffiliateMonthlyEarning.gross_revenue_cents), 0).label(
                    "gross_cents"
                ),
                func.coalesce(func.sum(AffiliateMonthlyEarning.commission_amount_cents), 0).label(
                    "commission_cents"
                ),
            )
            .filter(AffiliateMonthlyEarning.referrer_organization_id == organization.id)
            .group_by(AffiliateMonthlyEarning.earning_month)
            .all()
        )
        earnings_map = {
            row.earning_month.strftime("%Y-%m"): {
                "gross_cents": int(row.gross_cents or 0),
                "commission_cents": int(row.commission_cents or 0),
            }
            for row in earning_rows
            if row.earning_month
        }
        income_labels = []
        income_values = []
        gross_values = []
        commission_rate_values = []
        current_month = now.date().replace(day=1)
        for index in range(11, -1, -1):
            pointer = current_month
            for _ in range(index):
                prev = pointer - timedelta(days=1)
                pointer = prev.replace(day=1)
            map_key = pointer.strftime("%Y-%m")
            month_entry = earnings_map.get(map_key, {})
            month_commission = int(month_entry.get("commission_cents", 0) or 0)
            month_gross = int(month_entry.get("gross_cents", 0) or 0)
            commission_rate = (
                round((month_commission / month_gross) * 100.0, 2)
                if month_gross > 0
                else 0.0
            )
            income_labels.append(pointer.strftime("%b %Y"))
            income_values.append(month_commission)
            gross_values.append(month_gross)
            commission_rate_values.append(commission_rate)

        current_month_entry = earnings_map.get(now.strftime("%Y-%m"), {})
        current_month_income_cents = int(current_month_entry.get("commission_cents", 0) or 0)
        current_month_gross_cents = int(current_month_entry.get("gross_cents", 0) or 0)
        total_commission_12m = int(sum(income_values))
        total_gross_12m = int(sum(gross_values))
        effective_commission_rate_percent = (
            round((total_commission_12m / total_gross_12m) * 100.0, 2)
            if total_gross_12m > 0
            else 0.0
        )
        active_referrals = max(0, total_referrals - churned_count)
        churn_rate = (churned_count / total_referrals * 100.0) if total_referrals else 0.0
        avg_lifespan = (
            sum(lifespan_durations) / len(lifespan_durations) if lifespan_durations else 0.0
        )
        avg_to_churn = (
            sum(churn_durations) / len(churn_durations) if churn_durations else 0.0
        )
        retention_windows = []
        for window_days in retention_windows_days:
            tracker = retention_trackers[window_days]
            eligible = int(tracker["eligible"])
            retained = int(tracker["retained"])
            retained_percent = round((retained / eligible) * 100.0, 2) if eligible else 0.0
            retention_windows.append(
                {
                    "days": window_days,
                    "label": f"{window_days} days",
                    "eligible_count": eligible,
                    "retained_count": retained,
                    "retained_percent": retained_percent,
                }
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
                "effective_commission_rate_percent": float(effective_commission_rate_percent),
                "current_month_income_cents": int(current_month_income_cents),
                "current_month_income_display": cls._format_currency_cents(
                    current_month_income_cents
                ),
                "current_month_gross_cents": int(current_month_gross_cents),
                "current_month_gross_display": cls._format_currency_cents(
                    current_month_gross_cents
                ),
                "monthly_income_12m": {"labels": income_labels, "values": income_values},
                "monthly_commission_rate_12m": {
                    "labels": income_labels,
                    "values": commission_rate_values,
                },
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
                "retention_windows": retention_windows,
                "lifespan_buckets": {
                    "labels": list(lifespan_bucket_counts.keys()),
                    "values": [
                        lifespan_bucket_counts[label]
                        for label in lifespan_bucket_counts.keys()
                    ],
                },
            }
        )
        return payload
