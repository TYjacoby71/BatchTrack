"""Unit catalog helper service.

Synopsis:
Centralizes authenticated unit search/list serialization and org-scoped custom
unit creation so route handlers do not duplicate unit business rules.

Glossary:
- Custom unit: Organization-owned unit created by a user.
- Standard unit: Seeded/global unit available to all organizations.
"""

from __future__ import annotations

from sqlalchemy import func

from app.extensions import db
from app.models import Unit
from app.utils.unit_utils import get_global_unit_list

ALLOWED_UNIT_TYPES = {"weight", "volume", "count", "length", "area", "time"}
BASE_UNIT_BY_TYPE = {
    "weight": "gram",
    "volume": "ml",
    "count": "count",
    "length": "cm",
    "area": "sqcm",
    "time": "second",
}


def normalize_unit_type(unit_type: str | None, *, fallback: str = "count") -> str:
    normalized = (unit_type or fallback).strip().lower()
    return normalized if normalized in ALLOWED_UNIT_TYPES else fallback


def serialize_unit(unit: Unit) -> dict:
    return {
        "id": unit.id,
        "name": unit.name,
        "unit_type": unit.unit_type,
        "symbol": unit.symbol,
        "is_custom": bool(unit.is_custom),
        "base_unit": unit.base_unit,
        "is_mapped": bool(unit.is_mapped),
    }


def list_units(
    *, unit_type: str | None = None, query: str | None = None, limit: int = 50
) -> list[dict]:
    units = get_global_unit_list() or []
    normalized_type = normalize_unit_type(unit_type) if unit_type else None
    q = (query or "").strip().lower()

    if normalized_type:
        units = [u for u in units if getattr(u, "unit_type", None) == normalized_type]
    if q:
        units = [u for u in units if q in (getattr(u, "name", "") or "").lower()]

    units.sort(
        key=lambda u: (
            str(getattr(u, "unit_type", "") or ""),
            str(getattr(u, "name", "") or ""),
        )
    )
    return [
        {
            "id": getattr(u, "id", None),
            "name": getattr(u, "name", ""),
            "unit_type": getattr(u, "unit_type", None),
            "symbol": getattr(u, "symbol", None),
            "is_custom": bool(getattr(u, "is_custom", False)),
        }
        for u in units[: max(1, limit)]
    ]


def create_or_get_custom_unit(
    *,
    name: str,
    unit_type: str,
    organization_id: int,
    created_by: int | None,
    symbol: str | None = None,
    commit: bool = True,
) -> tuple[Unit, bool]:
    clean_name = (name or "").strip()
    if not clean_name:
        raise ValueError("Unit name is required")
    if not organization_id:
        raise ValueError("Organization is required for custom units")

    normalized_type = normalize_unit_type(unit_type)
    existing = Unit.query.filter(
        func.lower(Unit.name) == func.lower(db.literal(clean_name)),
        (Unit.is_custom.is_(False)) | (Unit.organization_id == organization_id),
    ).first()
    if existing:
        return existing, False

    try:
        unit = Unit(
            name=clean_name,
            symbol=(symbol or clean_name).strip()[:16],
            unit_type=normalized_type,
            conversion_factor=1.0,
            base_unit=BASE_UNIT_BY_TYPE.get(normalized_type, "count"),
            is_active=True,
            is_custom=True,
            is_mapped=False,
            organization_id=organization_id,
            created_by=created_by,
        )
        db.session.add(unit)
        if commit:
            db.session.commit()
        return unit, True
    except Exception:
        if commit:
            db.session.rollback()
        raise
