"""Developer add-on catalog service.

Synopsis:
Encapsulates add-on CRUD reads/writes so blueprint routes remain transport-focused
and avoid direct persistence calls.

Glossary:
- Add-on key: Unique immutable identifier for an add-on.
- Active add-on: Add-on available for tier inclusion/checkout.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models.addon import Addon


@dataclass(frozen=True)
class AddonUpsertPayload:
    key: str | None
    name: str
    description: str | None
    permission_name: str | None
    function_key: str | None
    billing_type: str
    stripe_lookup_key: str | None
    is_active: bool


class AddonService:
    """Service boundary for developer add-on catalog flows."""

    @staticmethod
    def list_addons() -> list[Addon]:
        return Addon.query.order_by(Addon.name).all()

    @staticmethod
    def get_addon(addon_id: int) -> Addon | None:
        return db.session.get(Addon, addon_id)

    @staticmethod
    def find_active_addon_by_key(key: str) -> Addon | None:
        return Addon.query.filter_by(key=key, is_active=True).first()

    @staticmethod
    def addon_key_exists(key: str) -> bool:
        return Addon.query.filter_by(key=key).first() is not None

    @staticmethod
    def parse_payload_from_form(form, *, require_key: bool) -> AddonUpsertPayload:
        key = (form.get("key") or "").strip() if require_key else None
        name = (form.get("name") or "").strip()
        description = form.get("description")
        permission_name = (form.get("permission_name") or "").strip() or None
        function_key = (form.get("function_key") or "").strip() or None
        billing_type = (form.get("billing_type") or "subscription").strip()
        stripe_lookup_key = (form.get("stripe_lookup_key") or "").strip() or None
        is_active = form.get("is_active") == "on"
        return AddonUpsertPayload(
            key=key,
            name=name,
            description=description,
            permission_name=permission_name,
            function_key=function_key,
            billing_type=billing_type,
            stripe_lookup_key=stripe_lookup_key,
            is_active=is_active,
        )

    @staticmethod
    def validate_create_payload(payload: AddonUpsertPayload) -> str | None:
        if not (payload.key or "").strip():
            return "Key is required"
        if not payload.name:
            return "Name is required"
        if AddonService.addon_key_exists(payload.key):  # type: ignore[arg-type]
            return "Addon key already exists"
        return None

    @staticmethod
    def create_addon(payload: AddonUpsertPayload) -> Addon:
        addon = Addon(
            key=payload.key,
            name=payload.name,
            description=payload.description,
            permission_name=payload.permission_name,
            function_key=payload.function_key,
            billing_type=payload.billing_type,
            stripe_lookup_key=payload.stripe_lookup_key,
            is_active=payload.is_active,
        )
        db.session.add(addon)
        db.session.commit()
        return addon

    @staticmethod
    def update_addon(addon: Addon, payload: AddonUpsertPayload) -> Addon:
        addon.name = payload.name or addon.name
        addon.description = payload.description
        addon.permission_name = payload.permission_name
        addon.function_key = payload.function_key
        addon.billing_type = payload.billing_type or addon.billing_type
        addon.stripe_lookup_key = payload.stripe_lookup_key
        addon.is_active = payload.is_active
        db.session.commit()
        return addon

    @staticmethod
    def delete_addon(addon: Addon) -> None:
        db.session.delete(addon)
        db.session.commit()
