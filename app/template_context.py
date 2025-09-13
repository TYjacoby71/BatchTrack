from flask import current_app, session, g
from flask_login import current_user
from flask_wtf.csrf import generate_csrf
from .utils.permissions import has_permission
from .utils.timezone_utils import TimezoneUtils
from app.utils.unit_utils import get_global_unit_list
from app.utils.cache_manager import app_cache
from .models import IngredientCategory


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

    @app.context_processor
    def _inject_marketing_content():
        """Inject public marketing content and stats for homepage."""
        import json, os
        from sqlalchemy import func
        try:
            from .models import Organization, User
            from .models.subscription_tier import SubscriptionTier
        except Exception:
            Organization = None
            User = None
            SubscriptionTier = None

        # Load reviews
        reviews = []
        try:
            if os.path.exists('data/reviews.json'):
                with open('data/reviews.json', 'r') as f:
                    reviews = json.load(f) or []
        except Exception:
            reviews = []

        # Load business spotlights
        spotlights = []
        try:
            if os.path.exists('data/spotlights.json'):
                with open('data/spotlights.json', 'r') as f:
                    all_spotlights = json.load(f) or []
                    # Only show approved
                    spotlights = [s for s in all_spotlights if s.get('approved')]
        except Exception:
            spotlights = []

        # Stats
        total_active_users = 0
        lifetime_total = 500
        lifetime_used = 0
        if User and Organization and SubscriptionTier:
            try:
                total_active_users = User.query.filter(
                    User.user_type != 'developer',
                    User.is_active == True
                ).count()

                # Lifetime seats: orgs on a tier with name like 'lifetime' OR whop_product_tier == 'lifetime'
                lifetime_tiers = SubscriptionTier.query.filter(SubscriptionTier.name.ilike('%lifetime%')).all()
                lifetime_tier_ids = [t.id for t in lifetime_tiers]
                lifetime_used = 0
                if lifetime_tier_ids:
                    lifetime_used += Organization.query.filter(Organization.subscription_tier_id.in_(lifetime_tier_ids)).count()
                # Include orgs flagged by whop tier
                try:
                    lifetime_used += Organization.query.filter(Organization.whop_product_tier == 'lifetime').count()
                except Exception:
                    pass
            except Exception:
                pass

        lifetime_left = max(0, lifetime_total - int(lifetime_used or 0))

        # Marketing messages (review asks day 1/3/5)
        messages = {'day_1': '', 'day_3': '', 'day_5': ''}
        marketing_settings = {'promo_codes': [], 'demo_url': '', 'demo_videos': []}
        try:
            if os.path.exists('settings.json'):
                with open('settings.json', 'r') as f:
                    cfg = json.load(f) or {}
                    messages.update(cfg.get('marketing_messages', {}))
                    marketing_settings['promo_codes'] = cfg.get('promo_codes', []) or []
                    marketing_settings['demo_url'] = cfg.get('demo_url', '') or ''
                    marketing_settings['demo_videos'] = cfg.get('demo_videos', []) or []
        except Exception:
            pass

        return dict(
            marketing_reviews=reviews,
            marketing_spotlights=spotlights,
            marketing_stats=dict(total_active_users=total_active_users, lifetime_left=lifetime_left, lifetime_total=lifetime_total),
            marketing_messages=messages,
            marketing_settings=marketing_settings,
        )

    @app.context_processor
    def _inject_ingredient_categories():
        def get_ingredient_categories():
            """Get ingredient categories for current user's organization"""
            from flask_login import current_user
            if not current_user.is_authenticated:
                return []
            return IngredientCategory.query.filter_by(
                organization_id=current_user.organization_id,
                is_active=True
            ).order_by(IngredientCategory.name).all()

        return dict(
            get_ingredient_categories=get_ingredient_categories
        )

    app.jinja_env.globals.update({
        'get_global_unit_list': get_global_unit_list,
        'get_ingredient_categories': lambda: IngredientCategory.query.filter_by(
            organization_id=current_user.organization_id if current_user.is_authenticated else None,
            is_active=True
        ).order_by(IngredientCategory.name).all() if current_user.is_authenticated else []
    })