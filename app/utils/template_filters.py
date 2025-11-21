from datetime import datetime
from typing import Any

from flask_login import current_user

from ..extensions import db
from ..models import Organization
from ..services.unit_conversion import ConversionEngine
from ..utils.timezone_utils import TimezoneUtils
from .duration_utils import humanize_duration_days
from app.filters.product_filters import (
    ingredient_cost_currency,
    product_variant_name,
    register_product_filters,
    safe_float,
)
from .permissions import (
    has_permission as perm_has_permission,
    has_role as perm_has_role,
    has_subscription_feature,
    is_developer,
    is_organization_owner as permissions_is_organization_owner,
)


def format_currency(value):
    """Format a number as currency"""
    if value is None:
        return "$0.00"
    try:
        return f"${float(value):.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def format_percentage(value, decimal_places=1):
    """Format a number as percentage"""
    if value is None:
        return "0%"
    try:
        return f"{float(value):.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0%"


def pluralize(count, singular, plural=None):
    """Return singular or plural form based on count"""
    if count == 1:
        return singular
    return plural or f"{singular}s"


def user_date(value, format_string="%Y-%m-%d"):
    """Format date in user's timezone"""
    if not value:
        return ""
    return TimezoneUtils.format_for_user(value, format_string)


def user_timezone(value, format_string="%Y-%m-%d %H:%M:%S"):
    """Format datetime in user's timezone"""
    if not value:
        return ""
    return TimezoneUtils.format_for_user(value, format_string)


def nl2br(value):
    """Convert newlines to HTML breaks"""
    if not value:
        return ""
    return value.replace('\n', '<br>\n')


def register_template_filters(app):
    """Register all custom Jinja2 filters and globals."""

    # --- Core timezone-aware filters -------------------------------------------------
    @app.template_filter("user_timezone")
    def user_timezone_filter(value, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
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

    @app.template_filter("user_datetime")
    def user_datetime_filter(value, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
        if not value:
            return ""
        return TimezoneUtils.format_for_user(value, format_string)

    @app.template_filter("user_date")
    def user_date_filter(value, format_string: str = "%Y-%m-%d") -> str:
        if not value:
            return ""
        return TimezoneUtils.format_for_user(value, format_string)

    @app.template_filter("user_time")
    def user_time_filter(value, format_string: str = "%H:%M:%S") -> str:
        if not value:
            return ""
        return TimezoneUtils.format_for_user(value, format_string)

    @app.template_filter("format_user_time")
    def format_user_time_filter(value, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
        if not value:
            return ""
        return TimezoneUtils.format_for_user(value, format_string)

    @app.template_filter("to_user_tz")
    def to_user_timezone_filter(value):
        if not value:
            return value
        return TimezoneUtils.to_user_timezone(value)

    # --- Date/number helpers --------------------------------------------------------
    @app.template_filter("timestamp_to_date")
    def timestamp_to_date_filter(value: Any) -> str:
        if not value:
            return "N/A"
        try:
            dt = datetime.fromtimestamp(value) if isinstance(value, (int, float)) else value
            aware = TimezoneUtils.ensure_timezone_aware(dt)
            return TimezoneUtils.format_for_user(aware, "%B %d, %Y")
        except Exception:
            return "Invalid date"

    @app.template_filter("from_symbol")
    def from_symbol_filter(symbol: str):
        if not symbol:
            return None
        try:
            engine = ConversionEngine()
            return engine.get_unit_by_symbol(symbol)
        except Exception:
            return None

    @app.template_filter("attr_multiply")
    def attr_multiply_filter(item, attr1: str, attr2: str):
        if item is None:
            return 0
        val1 = getattr(item, attr1, 0) or 0
        val2 = getattr(item, attr2, 0) or 0
        return float(val1) * float(val2)

    @app.template_filter("format_datetime")
    def format_datetime_filter(value) -> str:
        if not value:
            return "Never"
        user_tz = "UTC"
        if current_user.is_authenticated and getattr(current_user, "timezone", None):
            user_tz = current_user.timezone
        localized = TimezoneUtils.to_user_timezone(value, user_tz)
        return localized.strftime("%Y-%m-%d %H:%M:%S %Z")

    @app.template_filter("humanize_days")
    def humanize_days_filter(value, include_days: bool = True) -> str:
        return humanize_duration_days(value, include_days=include_days)

    # --- Template globals -----------------------------------------------------------
    @app.template_global("TimezoneUtils")
    def timezone_utils_global():
        return TimezoneUtils

    @app.template_global("get_grouped_timezones")
    def get_grouped_timezones_global():
        return TimezoneUtils.get_grouped_timezones()

    @app.template_global("get_available_timezones")
    def get_available_timezones_global():
        return TimezoneUtils.get_available_timezones()

    @app.template_global("get_organization_by_id")
    def get_organization_by_id(org_id: int):
        if org_id is None:
            return None
        return db.session.get(Organization, org_id)

    @app.template_global("is_organization_owner")
    def is_organization_owner_global():
        try:
            return permissions_is_organization_owner()
        except Exception:
            return False

    @app.template_global("has_permission")
    def has_permission_global(*args):
        try:
            if len(args) == 1:
                return perm_has_permission(current_user, args[0])
            if len(args) == 2:
                return perm_has_permission(args[0], args[1])
        except Exception:
            pass
        return False

    @app.template_global("has_role")
    def has_role_global(role_name: str) -> bool:
        try:
            return perm_has_role(role_name)
        except Exception:
            return False

    @app.template_global("has_tier_permission")
    def has_tier_permission_global(permission_name: str) -> bool:
        if not current_user.is_authenticated:
            return False
        organization = getattr(current_user, "organization", None)
        if not organization:
            return False
        try:
            from app.utils.permissions import AuthorizationHierarchy

            tier_permissions = AuthorizationHierarchy.get_tier_allowed_permissions(organization)
            return permission_name in tier_permissions
        except Exception:
            return False

    @app.template_global("get_current_tier")
    def get_current_tier_global():
        if not current_user.is_authenticated:
            return "free"
        organization = getattr(current_user, "organization", None)
        if not organization:
            return "free"
        return getattr(organization, "effective_subscription_tier", "free")

    @app.template_global("get_tier_features")
    def get_tier_features_global(tier_key: Any = None):
        from app.models.subscription_tier import SubscriptionTier

        try:
            if tier_key is None:
                tier_key = get_current_tier_global()
            try:
                tier_id = int(tier_key)
            except (TypeError, ValueError):
                tier_id = None

            tier = db.session.get(SubscriptionTier, tier_id) if tier_id is not None else None
            if not tier:
                return []
            return [p.name for p in getattr(tier, "permissions", [])]
        except Exception:
            return []

    @app.template_global("has_subscription_feature")
    def has_subscription_feature_global(feature: str) -> bool:
        try:
            return has_subscription_feature(feature)
        except Exception:
            return False

    @app.template_global("is_developer")
    def is_developer_global() -> bool:
        try:
            return is_developer()
        except Exception:
            return False

    @app.template_global("can_access_route")
    def can_access_route_global(_route: str) -> bool:
        # Legacy helper retained for compatibility.
        return True

    # --- Product filters -----------------------------------------------------------
    register_product_filters(app)
    app.jinja_env.filters.update(
        {
            "product_variant_name": product_variant_name,
            "ingredient_cost_currency": ingredient_cost_currency,
            "safe_float": safe_float,
            "nl2br": nl2br,
        }
    )

