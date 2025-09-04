from flask import current_app, session, g
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from .utils.permissions import has_permission
from .utils.timezone_utils import TimezoneUtils
from app.utils.unit_utils import get_global_unit_list
from app.utils.cache_manager import app_cache


def register_template_context(app):
    """Register all template context processors"""

    @app.context_processor
    def _inject_csrf():
        return dict(csrf_token=generate_csrf)

    @app.context_processor
    def _inject_permissions():
        return dict(has_permission=has_permission)

    @app.context_processor
    def _inject_units_and_categories():
        from .utils.unit_utils import get_global_unit_list
        from .models import IngredientCategory

        # Determine effective organization for scoping units (categories are global)
        try:
            if current_user and current_user.is_authenticated:
                if getattr(current_user, 'user_type', None) == 'developer':
                    effective_org_id = session.get('dev_selected_org_id')
                else:
                    effective_org_id = current_user.organization_id
            else:
                effective_org_id = None
        except Exception:
            effective_org_id = None

        units_cache_key = f"template:units:{effective_org_id or 'public'}"
        units = app_cache.get(units_cache_key)
        categories = app_cache.get("template:ingredient_categories")

        if units is None:
            try:
                units = get_global_unit_list()
                app_cache.set(units_cache_key, units, ttl=3600)
            except Exception:
                units = []

        if categories is None:
            try:
                categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
                app_cache.set("template:ingredient_categories", categories, ttl=3600)
            except Exception:
                categories = []

        return dict(
            units=units,
            categories=categories,
            global_units=units,
        )

    @app.context_processor
    def _inject_permissions():
        from .utils.permissions import (
            has_permission, has_role, has_subscription_feature,
            is_organization_owner, is_developer
        )
        from .services.reservation_service import ReservationService
        from .models import ProductSKU

        def get_reservation_summary(inventory_item_id):
            if not inventory_item_id:
                return {'available': 0.0, 'reserved': 0.0, 'total': 0.0, 'reservations': []}

            # Scope by organization to avoid cross-tenant leakage
            try:
                if current_user and current_user.is_authenticated:
                    if getattr(current_user, 'user_type', None) == 'developer':
                        effective_org_id = session.get('dev_selected_org_id')
                    else:
                        effective_org_id = current_user.organization_id
                else:
                    effective_org_id = None
            except Exception:
                effective_org_id = None

            cache_key = f'template:reservation_summary:{effective_org_id or "public"}:{inventory_item_id}'
            cached = app_cache.get(cache_key)
            if cached is not None:
                return cached

            sku = ProductSKU.query.filter_by(inventory_item_id=inventory_item_id).first()
            result = ReservationService.get_reservation_summary_for_sku(sku) if sku else {
                'available': 0.0, 'reserved': 0.0, 'total': 0.0, 'reservations': []
            }

            app_cache.set(cache_key, result, ttl=60)
            return result

        return dict(
            has_permission=has_permission,
            has_role=has_role,
            has_subscription_feature=has_subscription_feature,
            is_organization_owner=is_organization_owner,
            is_developer=is_developer,
            get_reservation_summary=get_reservation_summary,
            user_tier=lambda: (
                getattr(getattr(current_user, "organization", None), "subscription_tier", "free")
                if current_user.is_authenticated else "free"
            ),
        )

    @app.context_processor
    def _inject_org_helpers():
        from .models import Organization

        def get_organization_by_id(org_id):
            if not org_id:
                return None
            try:
                return app.extensions["sqlalchemy"].session.get(Organization, org_id)
            except Exception:
                return Organization.query.get(org_id)

        def get_current_organization():
            if not current_user.is_authenticated:
                return None
            if current_user.user_type == 'developer':
                org_id = session.get('dev_selected_org_id')
            else:
                org_id = current_user.organization_id
            return get_organization_by_id(org_id) if org_id else None

        def get_effective_org_id():
            if current_user.is_authenticated:
                if current_user.user_type == 'developer':
                    return session.get('dev_selected_org_id')
                return current_user.organization_id
            return None

        return dict(
            get_organization_by_id=get_organization_by_id,
            get_current_organization=get_current_organization,
            get_effective_org_id=get_effective_org_id,
        )

    @app.context_processor
    def _inject_timezone_utils():
        return dict(
            TimezoneUtils=TimezoneUtils,
            TimezoneUtils_global=TimezoneUtils,
            current_time=TimezoneUtils.utc_now,
        )

    app.jinja_env.globals.update({
        'get_global_unit_list': get_global_unit_list
    })