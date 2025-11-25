from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from flask import current_app

from ..extensions import db
from ..models import Addon, BatchBotCreditBundle, Organization


class BatchBotCreditError(RuntimeError):
    pass


@dataclass(slots=True)
class CreditSnapshot:
    total: int
    remaining: int
    expires_next: Optional[datetime]


class BatchBotCreditService:
    """Manages purchased BatchBot refills (per-organization credits)."""

    @staticmethod
    def grant_credits(
        *,
        organization: Organization,
        amount: int,
        source: str,
        reference: Optional[str] = None,
        addon: Optional[Addon] = None,
        metadata: Optional[dict] = None,
        expires_at: Optional[datetime] = None,
    ) -> BatchBotCreditBundle:
        if amount <= 0:
            raise BatchBotCreditError("Credit amount must be positive.")

        bundle = BatchBotCreditBundle(
            organization_id=organization.id,
            addon_id=addon.id if addon else None,
            source=source,
            reference=reference,
            purchased_requests=amount,
            remaining_requests=amount,
            metadata=metadata or {},
            expires_at=expires_at,
        )
        db.session.add(bundle)
        db.session.commit()
        return bundle

    @staticmethod
    def grant_signup_bonus(org: Organization, *, requests: Optional[int] = None) -> Optional[BatchBotCreditBundle]:
        bonus = requests if requests is not None else current_app.config.get("BATCHBOT_SIGNUP_BONUS_REQUESTS", 0)
        if bonus <= 0:
            return None

        existing = (
            BatchBotCreditBundle.query.filter_by(organization_id=org.id, source="signup_bonus")
            .order_by(BatchBotCreditBundle.created_at.asc())
            .first()
        )
        if existing:
            return None

        return BatchBotCreditService.grant_credits(
            organization=org,
            amount=bonus,
            source="signup_bonus",
            reference="initial_bonus",
            metadata={"reason": "Signup bonus"},
        )

    @staticmethod
    def grant_from_addon(org: Organization, addon: Addon, reference: Optional[str] = None) -> Optional[BatchBotCreditBundle]:
        amount = getattr(addon, "batchbot_credit_amount", 0) or 0
        if amount <= 0:
            return None
        return BatchBotCreditService.grant_credits(
            organization=org,
            amount=amount,
            source="addon",
            reference=reference or addon.key,
            addon=addon,
            metadata={"addon_name": addon.name},
        )

    @staticmethod
    def available_credits(org: Organization) -> int:
        now = datetime.utcnow()
        total = (
            db.session.query(db.func.coalesce(db.func.sum(BatchBotCreditBundle.remaining_requests), 0))
            .filter(
                BatchBotCreditBundle.organization_id == org.id,
                db.or_(
                    BatchBotCreditBundle.expires_at.is_(None),
                    BatchBotCreditBundle.expires_at > now,
                ),
                BatchBotCreditBundle.remaining_requests > 0,
            )
            .scalar()
        )
        return int(total or 0)

    @staticmethod
    def snapshot(org: Organization) -> CreditSnapshot:
        now = datetime.utcnow()
        bundles = (
            BatchBotCreditBundle.query.filter(
                BatchBotCreditBundle.organization_id == org.id,
                db.or_(
                    BatchBotCreditBundle.expires_at.is_(None),
                    BatchBotCreditBundle.expires_at > now,
                ),
            )
            .order_by(BatchBotCreditBundle.created_at.asc())
            .all()
        )
        total = sum(b.purchased_requests for b in bundles)
        remaining = sum(b.remaining_requests for b in bundles)
        next_expiry = min((b.expires_at for b in bundles if b.expires_at), default=None)
        return CreditSnapshot(total=total, remaining=remaining, expires_next=next_expiry)

    @staticmethod
    def consume(org: Organization, amount: int) -> None:
        if amount <= 0:
            return

        remaining = amount
        now = datetime.utcnow()
        bundles = (
            BatchBotCreditBundle.query.filter(
                BatchBotCreditBundle.organization_id == org.id,
                BatchBotCreditBundle.remaining_requests > 0,
                db.or_(
                    BatchBotCreditBundle.expires_at.is_(None),
                    BatchBotCreditBundle.expires_at > now,
                ),
            )
            .order_by(BatchBotCreditBundle.created_at.asc(), BatchBotCreditBundle.id.asc())
            .with_for_update()
            .all()
        )

        for bundle in bundles:
            if remaining <= 0:
                break
            take = min(bundle.remaining_requests, remaining)
            bundle.remaining_requests -= take
            remaining -= take

        if remaining > 0:
            db.session.rollback()
            raise BatchBotCreditError("Insufficient BatchBot credits.")

        db.session.commit()
