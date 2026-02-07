from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict

from flask import has_request_context
from flask_login import current_user

from ..extensions import db
from ..models import Organization
from ..services.unit_conversion import ConversionEngine
from ..utils.timezone_utils import TimezoneUtils
from .duration_utils import humanize_duration_days
from .permissions import (
    has_permission as perm_has_permission,
    has_role as perm_has_role,
    has_subscription_feature,
    is_developer,
    is_organization_owner as permissions_is_organization_owner,
)
from app.filters.product_filters import (
    ingredient_cost_currency,
    product_variant_name,
    register_product_filters,
    safe_float,
)
from app.utils.recipe_display import format_recipe_lineage_name

__all__ = ["register_template_filters"]


# ---------------------------------------------------------------------------
# Basic formatting helpers
# ---------------------------------------------------------------------------

def _format_currency(value: Any) -> str:
    if value is None:
        return "$0.00"
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _format_percentage(value: Any, decimal_places: int = 1) -> str:
    if value is None:
        return "0%"
    try:
        percentage = float(value)
    except (TypeError, ValueError):
        return "0%"
    return f"{percentage:.{decimal_places}f}%"


def _pluralize(count: Any, singular: str, plural: str | None = None) -> str:
    try:
        numeric = int(count)
    except (TypeError, ValueError):
        numeric = 0
    if numeric == 1:
        return singular
    return plural or f"{singular}s"


def _nl2br(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("\n", "<br>\n")


# ---------------------------------------------------------------------------
# Timezone-aware formatting
# ---------------------------------------------------------------------------

def _format_user_datetime(value: Any, format_string: str) -> str:
    if not value:
        return ""
    try:
        return TimezoneUtils.format_for_user(value, format_string)
    except Exception:
        try:
            aware = TimezoneUtils.ensure_timezone_aware(value)
            return aware.strftime(format_string)
        except Exception:
            return ""


def _user_timezone_filter(value: Any, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    return _format_user_datetime(value, format_string)


def _user_datetime_filter(value: Any, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    return _format_user_datetime(value, format_string)


def _user_date_filter(value: Any, format_string: str = "%Y-%m-%d") -> str:
    return _format_user_datetime(value, format_string)


def _user_time_filter(value: Any, format_string: str = "%H:%M:%S") -> str:
    return _format_user_datetime(value, format_string)


def _format_user_time_filter(value: Any, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    return _format_user_datetime(value, format_string)


def _to_user_timezone_filter(value: Any):
    if not value:
        return value
    return TimezoneUtils.to_user_timezone(value)


def _timestamp_to_date_filter(value: Any) -> str:
    if not value:
        return "N/A"
    try:
        dt_obj = datetime.fromtimestamp(value) if isinstance(value, (int, float)) else value
        aware = TimezoneUtils.ensure_timezone_aware(dt_obj)
        return TimezoneUtils.format_for_user(aware, "%B %d, %Y")
    except Exception:
        return "Invalid date"


def _current_user_timezone() -> str:
    if not has_request_context():
        return "UTC"
    try:
        if current_user.is_authenticated:
            timezone = getattr(current_user, "timezone", None)
            if timezone:
                return timezone
    except Exception:
        pass
    return "UTC"


def _format_datetime_filter(value: Any) -> str:
    if not value:
        return "Never"
    user_tz = _current_user_timezone()
    localized = TimezoneUtils.to_user_timezone(value, user_tz)
    return localized.strftime("%Y-%m-%d %H:%M:%S %Z") if localized else "Never"


# ---------------------------------------------------------------------------
# Miscellaneous filters
# ---------------------------------------------------------------------------

def _from_symbol_filter(symbol: str):
    if not symbol:
        return None
    try:
        engine = ConversionEngine()
        return engine.get_unit_by_symbol(symbol)
    except Exception:
        return None


def _attr_multiply_filter(item: Any, attr1: str, attr2: str):
    if item is None:
        return 0
    val1 = getattr(item, attr1, 0) or 0
    val2 = getattr(item, attr2, 0) or 0
    try:
        return float(val1) * float(val2)
    except (TypeError, ValueError):
        return 0


def _humanize_days_filter(value: Any, include_days: bool = True) -> str:
    return humanize_duration_days(value, include_days=include_days)


def _recipe_lineage_name_filter(recipe: Any, include_test_number: bool = False) -> str:
    return format_recipe_lineage_name(recipe, include_test_number=include_test_number)


# ---------------------------------------------------------------------------
# Template globals
# ---------------------------------------------------------------------------

def _timezone_utils_global():
    return TimezoneUtils


def _get_grouped_timezones_global():
    return TimezoneUtils.get_grouped_timezones()


def _get_available_timezones_global():
    return TimezoneUtils.get_available_timezones()


def _get_organization_by_id_global(org_id: int | None):
    if org_id is None:
        return None
    return db.session.get(Organization, org_id)


def _is_organization_owner_global() -> bool:
    try:
        return permissions_is_organization_owner()
    except Exception:
        return False


def _has_permission_global(*args) -> bool:
    try:
        if len(args) == 1:
            return perm_has_permission(current_user, args[0])
        if len(args) == 2:
            return perm_has_permission(args[0], args[1])
    except Exception:
        pass
    return False


def _has_role_global(role_name: str) -> bool:
    try:
        return perm_has_role(role_name)
    except Exception:
        return False


def _current_user_organization():
    if not has_request_context():
        return None
    try:
        if current_user.is_authenticated:
            return getattr(current_user, "organization", None)
    except Exception:
        return None
    return None


def _has_tier_permission_global(permission_name: str) -> bool:
    organization = _current_user_organization()
    if organization is None:
        return False
    try:
        from app.utils.permissions import AuthorizationHierarchy

        tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)
        return permission_name in tier_permissions
    except Exception:
        return False


def _get_current_tier_global() -> str:
    organization = _current_user_organization()
    if organization is None:
        return "free"
    return getattr(organization, "effective_subscription_tier", "free")


def _get_tier_features_global(tier_key: Any = None):
    from app.models.subscription_tier import SubscriptionTier

    try:
        target_key = tier_key if tier_key is not None else _get_current_tier_global()
        try:
            tier_id = int(target_key)
        except (TypeError, ValueError):
            tier_id = None

        tier = db.session.get(SubscriptionTier, tier_id) if tier_id is not None else None
        if not tier:
            return []
        return [permission.name for permission in getattr(tier, "permissions", [])]
    except Exception:
        return []


def _has_subscription_feature_global(feature: str) -> bool:
    try:
        return has_subscription_feature(feature)
    except Exception:
        return False


def _is_developer_global() -> bool:
    try:
        return is_developer()
    except Exception:
        return False


def _can_access_route_global(_route: str) -> bool:
    """
    Compatibility helper for templates that expect this global.
    Route-level authorization continues to happen in view logic.
    """
    return True


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register_template_filters(app) -> None:
    """Attach custom filters and globals to the provided Flask app."""

    register_product_filters(app)

    filter_map: Dict[str, Callable[..., Any]] = {
        "format_currency": _format_currency,
        "format_percentage": _format_percentage,
        "pluralize": _pluralize,
        "nl2br": _nl2br,
        "user_timezone": _user_timezone_filter,
        "user_datetime": _user_datetime_filter,
        "user_date": _user_date_filter,
        "user_time": _user_time_filter,
        "format_user_time": _format_user_time_filter,
        "to_user_tz": _to_user_timezone_filter,
        "timestamp_to_date": _timestamp_to_date_filter,
        "from_symbol": _from_symbol_filter,
        "attr_multiply": _attr_multiply_filter,
        "format_datetime": _format_datetime_filter,
        "humanize_days": _humanize_days_filter,
        "lineage_recipe_name": _recipe_lineage_name_filter,
        # Product-specific filters registered via shared module
        "product_variant_name": product_variant_name,
        "ingredient_cost_currency": ingredient_cost_currency,
        "safe_float": safe_float,
    }

    app.jinja_env.filters.update(filter_map)

    app.jinja_env.globals.update(
        {
            "TimezoneUtils": _timezone_utils_global,
            "get_grouped_timezones": _get_grouped_timezones_global,
            "get_available_timezones": _get_available_timezones_global,
            "get_organization_by_id": _get_organization_by_id_global,
            "is_organization_owner": _is_organization_owner_global,
            "has_permission": _has_permission_global,
            "has_role": _has_role_global,
            "has_tier_permission": _has_tier_permission_global,
            "get_current_tier": _get_current_tier_global,
            "get_tier_features": _get_tier_features_global,
            "has_subscription_feature": _has_subscription_feature_global,
            "is_developer": _is_developer_global,
            "can_access_route": _can_access_route_global,
        }
    )
