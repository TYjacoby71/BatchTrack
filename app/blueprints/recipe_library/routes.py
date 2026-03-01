"""Public recipe library routes.

Synopsis:
Serve public marketplace listings, recipe detail, and org storefront views.

Glossary:
- Marketplace listing: Published recipe visible in the public library.
- Origin org: Organization that published the recipe.
"""

from __future__ import annotations
import logging

from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, nullslast, or_
from sqlalchemy.orm import joinedload

from app.extensions import cache, db, limiter
from app.models import Organization, ProductCategory, Recipe
from app.models.statistics import BatchStats
from app.services.cache_invalidation import recipe_library_cache_key
from app.services.statistics import AnalyticsDataService
from app.utils.cache_utils import should_bypass_cache, stable_cache_key
from app.utils.permissions import _org_tier_includes_permission
from app.utils.seo import slugify_value
from app.utils.settings import is_feature_enabled

logger = logging.getLogger(__name__)


recipe_library_bp = Blueprint("recipe_library_bp", __name__)

RECIPE_PURCHASE_PERMISSION = "recipes.purchase_options"
RECIPE_MARKETPLACE_PERMISSION = "recipes.marketplace_dashboard"
RECIPE_MARKETPLACE_DISPLAY_FLAG = "FEATURE_RECIPE_MARKETPLACE_DISPLAY"
PUBLIC_RECIPE_SEARCH_LIMIT = 10
PUBLIC_RECIPE_DETAIL_LIMIT = 10
PUBLIC_RECIPE_WINDOW_HOURS = 24


def _org_allows_permission(org: Organization | None, permission_name: str) -> bool:
    if not org:
        return False
    try:
        return _org_tier_includes_permission(org, permission_name)
    except Exception:
        logger.warning("Suppressed exception fallback at app/blueprints/recipe_library/routes.py:55", exc_info=True)
        return False


def _marketplace_display_enabled() -> bool:
    return is_feature_enabled(RECIPE_MARKETPLACE_DISPLAY_FLAG)


def _advance_public_counter(key: str, limit: int) -> tuple[bool, int]:
    """Advance an anonymous preview counter and return (allowed, remaining)."""
    record = session.get(key) or {}
    now = datetime.now(timezone.utc)
    try:
        last_ts = record.get("timestamp")
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if now - last_dt > timedelta(hours=PUBLIC_RECIPE_WINDOW_HOURS):
                record = {}
    except Exception:
        logger.warning("Suppressed exception fallback at app/blueprints/recipe_library/routes.py:73", exc_info=True)
        record = {}
    count = int(record.get("count") or 0)
    if count >= limit:
        return False, 0
    count += 1
    record["count"] = count
    record["timestamp"] = now.isoformat()
    session[key] = record
    return True, max(0, limit - count)


def _remaining_public_counter(key: str, limit: int) -> int:
    """Return remaining anonymous preview allowance for the active window."""
    record = session.get(key) or {}
    try:
        last_ts = record.get("timestamp")
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if datetime.now(timezone.utc) - last_dt > timedelta(
                hours=PUBLIC_RECIPE_WINDOW_HOURS
            ):
                return limit
    except Exception:
        logger.warning("Suppressed exception fallback at app/blueprints/recipe_library/routes.py:96", exc_info=True)
        return limit
    count = int(record.get("count") or 0)
    return max(0, limit - count)


# =========================================================
# PUBLIC LIBRARY
# =========================================================
# --- Library index ---
# Purpose: Render the public recipe library landing page.
@recipe_library_bp.route("/recipes/library")
@limiter.limit("60000/hour;5000/minute")
def recipe_library():
    if not _marketplace_display_enabled():
        abort(404)
    search_query = (request.args.get("search") or "").strip()
    category_filter = _safe_int(request.args.get("category"))
    sale_filter = (request.args.get("sale") or "any").lower()
    org_filter = _safe_int(request.args.get("organization"))
    origin_filter = (request.args.get("origin") or "any").lower()
    sort_mode = (request.args.get("sort") or "newest").lower()
    preview_remaining = None
    search_remaining = None

    if not current_user.is_authenticated:
        preview_remaining = _remaining_public_counter(
            "recipe_library_detail_views", PUBLIC_RECIPE_DETAIL_LIMIT
        )
        search_remaining = _remaining_public_counter(
            "recipe_library_search_views", PUBLIC_RECIPE_SEARCH_LIMIT
        )
        if search_query:
            allowed, remaining = _advance_public_counter(
                "recipe_library_search_views", PUBLIC_RECIPE_SEARCH_LIMIT
            )
            if not allowed:
                flash(
                    "Create a free account to keep searching the recipe library. You've reached the preview limit."
                )
                return redirect(
                    url_for(
                        "auth.quick_signup",
                        next=request.full_path,
                        source="recipe_library_rate_limit_cta",
                    )
                )
            search_remaining = remaining

    cache_payload = {
        "search": search_query or "",
        "category": category_filter or 0,
        "sale": sale_filter,
        "org": org_filter or 0,
        "origin": origin_filter,
        "sort": sort_mode,
    }
    raw_cache_key = stable_cache_key("recipe_library_public", cache_payload)
    cache_key = recipe_library_cache_key(raw_cache_key)

    if should_bypass_cache():
        cache.delete(cache_key)
    else:
        cached_page = cache.get(cache_key)
        if cached_page is not None:
            return cached_page

    query = (
        Recipe.query.options(
            joinedload(Recipe.product_category),
            joinedload(Recipe.stats),
            joinedload(Recipe.organization),
        )
        .outerjoin(Organization, Recipe.organization_id == Organization.id)
        .filter(
            Recipe.is_public.is_(True),
            Recipe.status == "published",
            Recipe.marketplace_status == "listed",
            Recipe.test_sequence.is_(None),
            Recipe.is_archived.is_(False),
            Recipe.is_current.is_(True),
            (Organization.recipe_library_blocked.is_(False))
            | (Organization.recipe_library_blocked.is_(None)),
        )
    )

    if category_filter:
        query = query.filter(Recipe.category_id == category_filter)
    if sale_filter == "sale":
        query = query.filter(Recipe.is_for_sale.is_(True))
    elif sale_filter == "free":
        query = query.filter(Recipe.is_for_sale.is_(False))
    if org_filter:
        query = query.filter(Recipe.organization_id == org_filter)
    if origin_filter == "batchtrack":
        query = query.filter(Recipe.org_origin_type == "batchtrack_native")
    elif origin_filter == "purchased":
        query = query.filter(Recipe.org_origin_purchased.is_(True))
    elif origin_filter == "authored":
        query = query.filter(
            (Recipe.org_origin_type.in_(["authored", "published"]))
            | (Recipe.org_origin_type.is_(None))
        )

    if search_query:
        tokens = [token.strip() for token in search_query.split() if token.strip()]
        for token in tokens:
            like_expr = f"%{token}%"
            query = query.filter(
                or_(
                    Recipe.name.ilike(like_expr),
                    Recipe.public_description.ilike(like_expr),
                )
            )

    if sort_mode == "oldest":
        query = query.order_by(Recipe.updated_at.asc())
    elif sort_mode == "downloads":
        query = query.order_by(
            Recipe.download_count.desc(), Recipe.updated_at.desc(), Recipe.name.asc()
        )
    elif sort_mode == "price_high":
        query = query.order_by(
            nullslast(Recipe.sale_price.desc()), Recipe.updated_at.desc()
        )
    else:
        query = query.order_by(Recipe.updated_at.desc(), Recipe.name.asc())

    recipes = query.limit(30).all()
    cost_map = _fetch_cost_rollups([r.id for r in recipes])

    recipe_cards = [
        _serialize_recipe_for_public(recipe, cost_map.get(recipe.id))
        for recipe in recipes
    ]

    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    organizations = (
        db.session.query(Organization.id, Organization.name)
        .join(Recipe, Recipe.organization_id == Organization.id)
        .filter(
            Recipe.is_public.is_(True),
            Recipe.status == "published",
            Recipe.marketplace_status == "listed",
            Recipe.test_sequence.is_(None),
            Recipe.is_archived.is_(False),
            Recipe.is_current.is_(True),
            (Organization.recipe_library_blocked.is_(False))
            | (Organization.recipe_library_blocked.is_(None)),
        )
        .distinct()
        .order_by(Organization.name.asc())
        .all()
    )
    org_options = [{"id": org.id, "name": org.name} for org in organizations]

    stats = AnalyticsDataService.get_recipe_library_metrics(force_refresh=False)
    # Ensure all required stats have default values
    stats.setdefault("total_public", 0)
    stats.setdefault("total_for_sale", 0)
    stats.setdefault("average_sale_price", 0.0)
    stats.setdefault("sale_percentage", 0)
    stats.setdefault("blocked_listings", 0)
    stats.setdefault("total_downloads", 0)
    stats.setdefault("total_purchases", 0)
    stats.setdefault("batchtrack_native_count", 0)

    rendered = render_template(
        "library/recipe_library.html",
        recipes=recipe_cards,
        categories=categories,
        stats=stats,
        organizations=org_options,
        search_query=search_query,
        category_filter=category_filter,
        sale_filter=sale_filter,
        org_filter=org_filter,
        origin_filter=origin_filter,
        sort_mode=sort_mode,
        preview_remaining=preview_remaining,
        search_remaining=search_remaining,
        show_public_header=True,
        lightweight_public_shell=True,
    )
    cache.set(
        cache_key,
        rendered,
        timeout=current_app.config.get("RECIPE_LIBRARY_CACHE_TTL", 180),
    )
    return rendered


# --- Recipe detail ---
# Purpose: Render public recipe detail page.
@recipe_library_bp.route("/recipes/library/<int:recipe_id>-<slug>")
def recipe_library_detail(recipe_id: int, slug: str):
    if not _marketplace_display_enabled():
        abort(404)
    preview_remaining = None
    if not current_user.is_authenticated:
        allowed, preview_remaining = _advance_public_counter(
            "recipe_library_detail_views", PUBLIC_RECIPE_DETAIL_LIMIT
        )
        if not allowed:
            flash(
                "Create a free account to keep exploring recipes. You've reached the preview limit."
            )
            return redirect(
                url_for(
                    "auth.quick_signup",
                    next=request.path,
                    source="recipe_library_rate_limit_cta",
                )
            )

    recipe = (
        Recipe.query.options(
            joinedload(Recipe.product_category),
            joinedload(Recipe.stats),
        )
        .outerjoin(Organization, Recipe.organization_id == Organization.id)
        .filter(
            Recipe.id == recipe_id,
            Recipe.is_public.is_(True),
            Recipe.status == "published",
            Recipe.marketplace_status == "listed",
            Recipe.test_sequence.is_(None),
            Recipe.is_archived.is_(False),
            Recipe.is_current.is_(True),
            (Organization.recipe_library_blocked.is_(False))
            | (Organization.recipe_library_blocked.is_(None)),
        )
        .first_or_404()
    )

    canonical_slug = slugify_value(recipe.name)
    if slug != canonical_slug:
        return redirect(
            url_for(
                "recipe_library_bp.recipe_library_detail",
                recipe_id=recipe_id,
                slug=canonical_slug,
            ),
            code=301,
        )

    cost_map = _fetch_cost_rollups([recipe.id])
    stats = _serialize_recipe_for_public(recipe, cost_map.get(recipe.id))
    marketplace_display_enabled = _marketplace_display_enabled()
    purchase_enabled = marketplace_display_enabled and _org_allows_permission(
        recipe.organization, RECIPE_PURCHASE_PERMISSION
    )
    org_marketplace_enabled = marketplace_display_enabled and _org_allows_permission(
        recipe.organization, RECIPE_MARKETPLACE_PERMISSION
    )
    reveal_details = False
    if getattr(current_user, "is_authenticated", False):
        if current_user.user_type == "developer" or session.get("dev_selected_org_id"):
            reveal_details = True

    return render_template(
        "library/recipe_detail.html",
        recipe=stats,
        purchase_enabled=purchase_enabled,
        reveal_details=reveal_details,
        org_marketplace_enabled=org_marketplace_enabled,
        preview_remaining=preview_remaining,
        show_public_header=True,
        lightweight_public_shell=True,
    )


# --- Organization library ---
# Purpose: Render public recipe list for a specific organization.
@recipe_library_bp.route("/recipes/library/organizations/<int:organization_id>")
def organization_marketplace(organization_id: int):
    if not _marketplace_display_enabled():
        abort(404)
    org = Organization.query.get_or_404(organization_id)
    if not _org_allows_permission(org, RECIPE_MARKETPLACE_PERMISSION):
        abort(404)
    if org.recipe_library_blocked:
        abort(404)

    search_query = (request.args.get("search") or "").strip()
    sale_filter = (request.args.get("sale") or "any").lower()
    sort_mode = (request.args.get("sort") or "newest").lower()

    query = Recipe.query.options(
        joinedload(Recipe.product_category),
        joinedload(Recipe.stats),
    ).filter(
        Recipe.organization_id == org.id,
        Recipe.is_public.is_(True),
        Recipe.status == "published",
        Recipe.marketplace_status == "listed",
        Recipe.test_sequence.is_(None),
        Recipe.is_archived.is_(False),
        Recipe.is_current.is_(True),
    )

    if sale_filter == "sale":
        query = query.filter(Recipe.is_for_sale.is_(True))
    elif sale_filter == "free":
        query = query.filter(Recipe.is_for_sale.is_(False))

    if search_query:
        tokens = [token.strip() for token in search_query.split() if token.strip()]
        for token in tokens:
            like_expr = f"%{token}%"
            query = query.filter(
                or_(
                    Recipe.name.ilike(like_expr),
                    Recipe.public_description.ilike(like_expr),
                )
            )

    if sort_mode == "downloads":
        query = query.order_by(
            Recipe.download_count.desc(), Recipe.updated_at.desc(), Recipe.name.asc()
        )
    elif sort_mode == "price_high":
        query = query.order_by(
            nullslast(Recipe.sale_price.desc()), Recipe.updated_at.desc()
        )
    elif sort_mode == "oldest":
        query = query.order_by(Recipe.updated_at.asc())
    else:
        query = query.order_by(Recipe.updated_at.desc(), Recipe.name.asc())

    recipes = query.all()
    cost_map = _fetch_cost_rollups([r.id for r in recipes])
    recipe_cards = [
        _serialize_recipe_for_public(recipe, cost_map.get(recipe.id))
        for recipe in recipes
    ]

    totals = {
        "listings": len(recipe_cards),
        "for_sale": len([r for r in recipe_cards if r["is_for_sale"]]),
        "downloads": sum(r["download_count"] for r in recipe_cards),
        "purchases": sum(r["purchase_count"] for r in recipe_cards),
    }

    return render_template(
        "library/organization_marketplace.html",
        organization=org,
        recipes=recipe_cards,
        totals=totals,
        purchase_enabled=_marketplace_display_enabled()
        and _org_allows_permission(org, RECIPE_PURCHASE_PERMISSION),
        search_query=search_query,
        sale_filter=sale_filter,
        sort_mode=sort_mode,
        show_public_header=True,
        lightweight_public_shell=True,
    )


def _serialize_recipe_for_public(
    recipe: Recipe, cost_rollup: dict | None = None
) -> dict:
    stats = recipe.stats[0] if getattr(recipe, "stats", None) else None
    cover_url = None
    if recipe.cover_image_path:
        cover_url = url_for("static", filename=recipe.cover_image_path)
    elif recipe.cover_image_url:
        cover_url = recipe.cover_image_url

    yield_per_dollar = None
    if (
        stats
        and stats.avg_cost_per_batch
        and stats.avg_cost_per_batch > 0
        and recipe.predicted_yield
    ):
        yield_per_dollar = float(recipe.predicted_yield or 0) / float(
            stats.avg_cost_per_batch
        )

    ingredient_cost = None
    total_cost = None
    if cost_rollup:
        ingredient_cost = cost_rollup.get("ingredient_cost")
        total_cost = cost_rollup.get("total_cost")

    marketplace_display_enabled = _marketplace_display_enabled()
    org_purchase_enabled = marketplace_display_enabled and _org_allows_permission(
        recipe.organization, RECIPE_PURCHASE_PERMISSION
    )
    org_marketplace_enabled = marketplace_display_enabled and _org_allows_permission(
        recipe.organization, RECIPE_MARKETPLACE_PERMISSION
    )
    return {
        "id": recipe.id,
        "slug": slugify_value(recipe.name),
        "name": recipe.name,
        "category": recipe.product_category.name if recipe.product_category else None,
        "is_for_sale": recipe.is_for_sale,
        "sale_price": (
            float(recipe.sale_price) if recipe.sale_price is not None else None
        ),
        "product_store_url": recipe.product_store_url,
        "cover_url": cover_url,
        "instructions": recipe.instructions,
        "predicted_yield": recipe.predicted_yield,
        "predicted_yield_unit": recipe.predicted_yield_unit,
        "marketplace_notes": recipe.marketplace_notes,
        "public_description": recipe.public_description,
        "stats": stats,
        "yield_per_dollar": yield_per_dollar,
        "skin_opt_in": recipe.skin_opt_in,
        "updated_at": recipe.updated_at,
        "avg_ingredient_cost": ingredient_cost,
        "avg_total_cost": total_cost,
        "organization": {
            "id": recipe.organization_id,
            "name": recipe.organization.name if recipe.organization else None,
        },
        "purchase_enabled": org_purchase_enabled,
        "org_marketplace_enabled": org_marketplace_enabled,
        "origin": {
            "type": recipe.org_origin_type,
            "purchased": recipe.org_origin_purchased,
            "source_org_id": recipe.org_origin_source_org_id,
            "source_org_name": (
                recipe.org_origin_source_org.name
                if recipe.org_origin_source_org
                else None
            ),
        },
        "download_count": recipe.download_count,
        "purchase_count": recipe.purchase_count,
    }


def _safe_int(value):
    try:
        return int(value) if value not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None


def _fetch_cost_rollups(recipe_ids):
    if not recipe_ids:
        return {}
    rows = (
        db.session.query(
            BatchStats.recipe_id,
            func.avg(BatchStats.actual_ingredient_cost).label("ingredient_cost"),
            func.avg(BatchStats.total_actual_cost).label("total_cost"),
        )
        .filter(BatchStats.recipe_id.in_(recipe_ids))
        .group_by(BatchStats.recipe_id)
        .all()
    )
    return {
        row.recipe_id: {
            "ingredient_cost": float(row.ingredient_cost or 0),
            "total_cost": float(row.total_cost or 0),
        }
        for row in rows
    }
