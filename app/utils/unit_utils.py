from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Iterable, List

from flask import g, has_request_context, session
from flask_login import current_user
from sqlalchemy import or_
from sqlalchemy.orm import load_only

from ..extensions import db
from ..models import Unit
from .cache_manager import app_cache
from .validation_helpers import validate_density
from ..services.unit_conversion import ConversionEngine

logger = logging.getLogger(__name__)

_REQUEST_CACHE_ATTR = "_global_unit_list"
_CACHE_TTL_SECONDS = 3600
_SLOW_QUERY_THRESHOLD = 0.05

_UNIT_LOAD_COLUMNS = (
    Unit.id,
    Unit.name,
    Unit.unit_type,
    Unit.base_unit,
    Unit.conversion_factor,
    Unit.symbol,
    Unit.is_custom,
    Unit.is_mapped,
    Unit.organization_id,
    Unit.created_by,
)


@dataclass(frozen=True)
class UnitOption:
    """Session-safe representation of a unit for caching/rendering."""

    id: int | None
    name: str
    unit_type: str = "count"
    base_unit: str | None = None
    conversion_factor: float | None = None
    symbol: str | None = None
    is_custom: bool = False
    is_mapped: bool = False
    organization_id: int | None = None
    created_by: int | None = None

    @property
    def is_base_unit(self) -> bool:
        return self.base_unit is None or self.base_unit == self.name


def _active_user():
    if not has_request_context():
        return None
    try:
        return current_user
    except Exception:
        return None


def _to_unit_option(unit: Any) -> UnitOption:
    """Convert ORM instances or dicts into a cache-safe representation."""
    if isinstance(unit, UnitOption):
        return unit
    return UnitOption(
        id=getattr(unit, "id", None),
        name=(getattr(unit, "name", "") or "").strip(),
        unit_type=getattr(unit, "unit_type", "count") or "count",
        base_unit=getattr(unit, "base_unit", None),
        conversion_factor=getattr(unit, "conversion_factor", None),
        symbol=getattr(unit, "symbol", None),
        is_custom=bool(getattr(unit, "is_custom", False)),
        is_mapped=bool(getattr(unit, "is_mapped", False)),
        organization_id=getattr(unit, "organization_id", None),
        created_by=getattr(unit, "created_by", getattr(unit, "user_id", None)),
    )


def _normalize_unit_collection(units: Iterable[Any]) -> List[UnitOption]:
    return [_to_unit_option(unit) for unit in units if unit is not None]


def _cache_scope_token() -> str:
    user = _active_user()
    if not user or not getattr(user, "is_authenticated", False):
        return "public"

    org_id = getattr(user, "organization_id", None)
    if org_id:
        return f"org:{org_id}"

    if getattr(user, "user_type", None) == "developer" and has_request_context():
        selected_org = session.get("dev_selected_org_id")
        return f"dev:{selected_org}" if selected_org else "dev:all"

    return "public"


def _cache_key() -> str:
    return f"units:{_cache_scope_token()}"


def _get_request_cache() -> List[UnitOption] | None:
    return getattr(g, _REQUEST_CACHE_ATTR, None) if has_request_context() else None


def _set_request_cache(units: List[UnitOption]) -> None:
    if has_request_context():
        setattr(g, _REQUEST_CACHE_ATTR, units)


def _fallback_units() -> List[UnitOption]:
    return [
        UnitOption(id=None, name="oz", unit_type="weight", base_unit="oz"),
        UnitOption(id=None, name="g", unit_type="weight", base_unit="g"),
        UnitOption(id=None, name="lb", unit_type="weight", base_unit="lb"),
        UnitOption(id=None, name="ml", unit_type="volume", base_unit="ml"),
        UnitOption(id=None, name="fl oz", unit_type="volume", base_unit="fl oz"),
        UnitOption(id=None, name="count", unit_type="count", base_unit="count"),
    ]


def _build_unit_query():
    query = (
        db.session.query(Unit)
        .options(load_only(*_UNIT_LOAD_COLUMNS))
        .filter(Unit.is_active.is_(True))
    )
    user = _active_user()
    base_scope = Unit.is_custom.is_(False)

    if not user or not getattr(user, "is_authenticated", False):
        return query.filter(base_scope).order_by(Unit.unit_type.asc(), Unit.name.asc())

    org_id = getattr(user, "organization_id", None)
    if org_id:
        scope_filter = or_(base_scope, Unit.organization_id == org_id)
    elif getattr(user, "user_type", None) == "developer" and has_request_context():
        selected_org = session.get("dev_selected_org_id")
        if selected_org:
            scope_filter = or_(base_scope, Unit.organization_id == selected_org)
        else:
            scope_filter = base_scope
    else:
        scope_filter = base_scope

    return query.filter(scope_filter).order_by(Unit.unit_type.asc(), Unit.name.asc())


def _fetch_units() -> List[Unit]:
    start = time.perf_counter()
    units = _build_unit_query().all()
    duration = time.perf_counter() - start
    if duration > _SLOW_QUERY_THRESHOLD:
        logger.warning("Unit query took %.3fs for %d units", duration, len(units))
    return units


def get_global_unit_list() -> List[UnitOption]:
    """Return active units, including organization-specific custom units."""
    request_cached = _get_request_cache()
    if request_cached:
        return request_cached

    cache_key = _cache_key()
    cached_units = app_cache.get(cache_key)
    if cached_units:
        safe_units = _normalize_unit_collection(cached_units)
        _set_request_cache(safe_units)
        if cached_units and not isinstance(cached_units[0], UnitOption):
            app_cache.set(cache_key, safe_units, _CACHE_TTL_SECONDS)
        return safe_units

    try:
        safe_units = _normalize_unit_collection(_fetch_units())
    except Exception as exc:
        logger.exception("Error getting global unit list: %s", exc)
        fallback = _fallback_units()
        _set_request_cache(fallback)
        app_cache.set(cache_key, fallback, _CACHE_TTL_SECONDS)
        return fallback

    if not safe_units:
        logger.warning("No units found for scope %s; using fallback set", cache_key)
        fallback = _fallback_units()
        _set_request_cache(fallback)
        app_cache.set(cache_key, fallback, _CACHE_TTL_SECONDS)
        return fallback

    _set_request_cache(safe_units)
    app_cache.set(cache_key, safe_units, _CACHE_TTL_SECONDS)
    return safe_units


def _ingredient_has_density(ingredient: Any | None) -> bool:
    if not ingredient:
        return False

    density = validate_density(getattr(ingredient, "density", None))
    if density is not None:
        return True

    category = getattr(ingredient, "category", None)
    if category:
        category_density = validate_density(getattr(category, "default_density", None))
        if category_density is not None:
            return True

    return False


def validate_density_requirements(
    from_unit: Any, to_unit: Any, ingredient: Any | None = None
) -> tuple[bool, str | None]:
    """Backward-compatible shim that delegates to ConversionEngine."""
    return ConversionEngine.validate_density_requirements(from_unit, to_unit, ingredient)