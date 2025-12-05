from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from flask import Flask, current_app, session
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from app.extensions import db
from app.utils.cache_manager import app_cache
from app.utils.unit_utils import get_global_unit_list

from .utils.json_store import read_json_file
from .utils.settings import is_feature_enabled
from .utils.permissions import (
    has_permission,
    has_role,
    has_subscription_feature,
    is_developer,
    is_organization_owner,
)
from .utils.timezone_utils import TimezoneUtils

_REVIEWS_PATH = Path("data/reviews.json")
_SPOTLIGHTS_PATH = Path("data/spotlights.json")
_SETTINGS_PATH = Path("settings.json")


def _serialize_ingredient_category(category) -> Dict[str, Any]:
    """Return a cache-safe representation of IngredientCategory."""
    if isinstance(category, dict):
        return category
    return {
        "id": getattr(category, "id", None),
        "name": getattr(category, "name", None),
        "organization_id": getattr(category, "organization_id", None),
        "is_active": getattr(category, "is_active", None),
        "is_global_category": getattr(category, "is_global_category", None),
        "description": getattr(category, "description", None),
    }


def _normalize_cached_categories(raw) -> list[Dict[str, Any]]:
    if not raw:
        return []
    return [_serialize_ingredient_category(cat) for cat in raw]


def register_template_context(app: Flask) -> None:
    """Register globally available template context helpers."""

    @app.context_processor
    def _inject_csrf() -> Dict[str, Any]:
        return {"csrf_token": generate_csrf}

    @app.context_processor
    def _inject_units_and_categories() -> Dict[str, Any]:
        from .models import IngredientCategory

        org_id = _effective_org_id()
        units_cache_key = f"template:units:{org_id or 'public'}"
        units = app_cache.get(units_cache_key)
        categories = app_cache.get("template:ingredient_categories")

        if units is None:
            try:
                units = get_global_unit_list()
            except Exception:
                units = []
            app_cache.set(units_cache_key, units, ttl=3600)

        # Older cache entries may still contain ORM rows; normalize aggressively.
        categories = _normalize_cached_categories(categories)
        if not categories:
            try:
                raw_categories = (
                    IngredientCategory.query.filter_by(
                        organization_id=None,
                        is_active=True,
                        is_global_category=True,
                    )
                    .order_by(IngredientCategory.name)
                    .all()
                )
            except Exception:
                raw_categories = []
            categories = _normalize_cached_categories(raw_categories)
            app_cache.set("template:ingredient_categories", categories, ttl=3600)

        return {"units": units, "global_units": units, "categories": categories}

    @app.context_processor
    def _inject_permission_helpers() -> Dict[str, Any]:
        from .models import ProductSKU
        from .services.reservation_service import ReservationService

        def get_reservation_summary(inventory_item_id: Any) -> Dict[str, Any]:
            if not inventory_item_id:
                return {"available": 0.0, "reserved": 0.0, "total": 0.0, "reservations": []}

            org_id = _effective_org_id()
            cache_key = f"template:reservation_summary:{org_id or 'public'}:{inventory_item_id}"
            cached = app_cache.get(cache_key)
            if cached is not None:
                return cached

            sku = ProductSKU.query.filter_by(inventory_item_id=inventory_item_id).first()
            summary = (
                ReservationService.get_reservation_summary_for_sku(sku)
                if sku
                else {"available": 0.0, "reserved": 0.0, "total": 0.0, "reservations": []}
            )
            app_cache.set(cache_key, summary, ttl=60)
            return summary

        def user_tier() -> str:
            if not current_user.is_authenticated:
                return "free"
            org = getattr(current_user, "organization", None)
            return getattr(org, "subscription_tier", "free")

        return {
            "has_permission": has_permission,
            "has_role": has_role,
            "has_subscription_feature": has_subscription_feature,
            "is_organization_owner": is_organization_owner,
            "is_developer": is_developer,
            "get_reservation_summary": get_reservation_summary,
            "user_tier": user_tier,
            "is_feature_enabled": is_feature_enabled,
        }

    @app.context_processor
    def _inject_org_helpers() -> Dict[str, Any]:
        from .models import Organization

        def get_organization_by_id(org_id: Any):
            if not org_id:
                return None
            try:
                return app.extensions["sqlalchemy"].session.get(Organization, org_id)
            except Exception:
                return db.session.get(Organization, org_id)

        def get_current_organization():
            org_id = _effective_org_id()
            return get_organization_by_id(org_id) if org_id else None

        return {
            "get_organization_by_id": get_organization_by_id,
            "get_current_organization": get_current_organization,
            "get_effective_org_id": _effective_org_id,
        }

    @app.context_processor
    def _inject_timezone_utils() -> Dict[str, Any]:
        return {
            "TimezoneUtils": TimezoneUtils,
            "TimezoneUtils_global": TimezoneUtils,
            "current_time": TimezoneUtils.utc_now,
        }

    @app.context_processor
    def _inject_marketing_content() -> Dict[str, Any]:
        try:
            from .models import Organization, User
            from .models.subscription_tier import SubscriptionTier
        except Exception:
            Organization = User = SubscriptionTier = None

        reviews = read_json_file(_REVIEWS_PATH, default=[]) or []
        all_spotlights = read_json_file(_SPOTLIGHTS_PATH, default=[]) or []
        spotlights = [spotlight for spotlight in all_spotlights if spotlight.get("approved")]

        total_active_users = 0
        lifetime_total = 500
        lifetime_used = 0
        if all((Organization, User, SubscriptionTier)):
            try:
                active_user_cache_key = "marketing:active_users"
                cached_total_users = app_cache.get(active_user_cache_key)
                if cached_total_users is None:
                    total_active_users = (
                        User.query.filter(User.user_type != "developer", User.is_active.is_(True)).count()
                    )
                    app_cache.set(active_user_cache_key, total_active_users, ttl=600)
                else:
                    total_active_users = cached_total_users
                lifetime_tiers = SubscriptionTier.query.filter(
                    SubscriptionTier.name.ilike("%lifetime%")
                ).all()
                tier_ids = [tier.id for tier in lifetime_tiers]
                if tier_ids:
                    lifetime_used += Organization.query.filter(
                        Organization.subscription_tier_id.in_(tier_ids)
                    ).count()
                lifetime_used += Organization.query.filter(
                    Organization.whop_product_tier == "lifetime"
                ).count()
            except Exception:
                pass

        lifetime_left = max(0, lifetime_total - int(lifetime_used or 0))

        cfg = read_json_file(_SETTINGS_PATH, default={}) or {}
        marketing_messages = {"day_1": "", "day_3": "", "day_5": ""}
        marketing_messages.update(cfg.get("marketing_messages", {}))
        marketing_settings = {
            "promo_codes": cfg.get("promo_codes", []) or [],
            "demo_url": cfg.get("demo_url", "") or "",
            "demo_videos": cfg.get("demo_videos", []) or [],
        }

        return {
            "marketing_reviews": reviews,
            "marketing_spotlights": spotlights,
            "marketing_stats": {
                "total_active_users": total_active_users,
                "lifetime_left": lifetime_left,
                "lifetime_total": lifetime_total,
            },
            "marketing_messages": marketing_messages,
            "marketing_settings": marketing_settings,
        }

    app.jinja_env.globals.update({"get_global_unit_list": get_global_unit_list})
    app.add_template_filter(static_file_exists_filter, "static_file_exists")


def static_file_exists_filter(relative_path: str) -> bool:
    """Check whether a file exists inside the configured static folder."""
    try:
        static_folder = Path(getattr(current_app, "static_folder", None) or "static")
        return (static_folder / relative_path).exists()
    except Exception:
        return False


def _effective_org_id():
    """Return the organization context for the current request."""
    if not current_user or not current_user.is_authenticated:
        return None
    if getattr(current_user, "user_type", None) == "developer":
        return session.get("dev_selected_org_id")
    return getattr(current_user, "organization_id", None)