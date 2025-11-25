from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for, abort, session
from flask_login import current_user
from sqlalchemy import func, or_, nullslast
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Recipe, ProductCategory, Organization
from app.models.statistics import RecipeStats, BatchStats
from app.models.recipe_marketplace import RecipeProductGroup
from app.services.statistics import AnalyticsDataService
from app.utils.seo import slugify_value
from app.utils.settings import is_feature_enabled

recipe_library_bp = Blueprint("recipe_library_bp", __name__)


@recipe_library_bp.route("/recipes/library")
def recipe_library():
    search_query = (request.args.get("search") or "").strip()
    group_filter = _safe_int(request.args.get("group"))
    category_filter = _safe_int(request.args.get("category"))
    sale_filter = (request.args.get("sale") or "any").lower()
    org_filter = _safe_int(request.args.get("organization"))
    origin_filter = (request.args.get("origin") or "any").lower()
    sort_mode = (request.args.get("sort") or "newest").lower()

    query = (
        Recipe.query.options(
            joinedload(Recipe.product_category),
            joinedload(Recipe.product_group),
            joinedload(Recipe.stats),
            joinedload(Recipe.organization),
        )
        .outerjoin(Organization, Recipe.organization_id == Organization.id)
        .filter(
            Recipe.is_public.is_(True),
            Recipe.status == "published",
            Recipe.marketplace_status == "listed",
            Recipe.marketplace_blocked.is_(False),
            (Organization.recipe_library_blocked.is_(False)) | (Organization.recipe_library_blocked.is_(None)),
        )
    )

    if group_filter:
        query = query.filter(Recipe.product_group_id == group_filter)
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
            (Recipe.org_origin_type == "authored") | (Recipe.org_origin_type.is_(None))
        )

    if search_query:
        tokens = [token.strip() for token in search_query.split() if token.strip()]
        for token in tokens:
            like_expr = f"%{token}%"
            query = query.filter(
                or_(
                    Recipe.name.ilike(like_expr),
                    Recipe.public_description.ilike(like_expr),
                    Recipe.marketplace_notes.ilike(like_expr),
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

    recipes = query.limit(60).all()
    cost_map = _fetch_cost_rollups([r.id for r in recipes])

    recipe_cards = [
        _serialize_recipe_for_public(recipe, cost_map.get(recipe.id))
        for recipe in recipes
    ]

    product_groups = (
        RecipeProductGroup.query.filter_by(is_active=True)
        .order_by(RecipeProductGroup.display_order.asc(), RecipeProductGroup.name.asc())
        .all()
    )
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    organizations = (
        db.session.query(Organization.id, Organization.name)
        .join(Recipe, Recipe.organization_id == Organization.id)
        .filter(
            Recipe.is_public.is_(True),
            Recipe.status == "published",
            Recipe.marketplace_status == "listed",
            Recipe.marketplace_blocked.is_(False),
            (Organization.recipe_library_blocked.is_(False))
            | (Organization.recipe_library_blocked.is_(None)),
        )
        .distinct()
        .order_by(Organization.name.asc())
        .all()
    )
    org_options = [{"id": org.id, "name": org.name} for org in organizations]

    stats = AnalyticsDataService.get_recipe_library_metrics()
    purchase_enabled = is_feature_enabled("FEATURE_RECIPE_PURCHASE_OPTIONS")
    org_marketplace_enabled = is_feature_enabled("FEATURE_ORG_MARKETPLACE_DASHBOARD")

    return render_template(
        "library/recipe_library.html",
        recipes=recipe_cards,
        product_groups=product_groups,
        categories=categories,
        stats=stats,
        purchase_enabled=purchase_enabled,
        organizations=org_options,
        org_marketplace_enabled=org_marketplace_enabled,
        search_query=search_query,
        group_filter=group_filter,
        category_filter=category_filter,
        sale_filter=sale_filter,
        org_filter=org_filter,
        origin_filter=origin_filter,
        sort_mode=sort_mode,
    )


@recipe_library_bp.route("/recipes/library/<int:recipe_id>-<slug>")
def recipe_library_detail(recipe_id: int, slug: str):
    recipe = (
        Recipe.query.options(
            joinedload(Recipe.product_category),
            joinedload(Recipe.product_group),
            joinedload(Recipe.stats),
        )
        .outerjoin(Organization, Recipe.organization_id == Organization.id)
        .filter(
            Recipe.id == recipe_id,
            Recipe.is_public.is_(True),
            Recipe.marketplace_status == "listed",
            Recipe.marketplace_blocked.is_(False),
            (Organization.recipe_library_blocked.is_(False)) | (Organization.recipe_library_blocked.is_(None)),
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
    purchase_enabled = is_feature_enabled("FEATURE_RECIPE_PURCHASE_OPTIONS")
    reveal_details = False
    if getattr(current_user, "is_authenticated", False):
        if current_user.user_type == "developer" or session.get("dev_selected_org_id"):
            reveal_details = True

    return render_template(
        "library/recipe_detail.html",
        recipe=stats,
        purchase_enabled=purchase_enabled,
        reveal_details=reveal_details,
        org_marketplace_enabled=is_feature_enabled("FEATURE_ORG_MARKETPLACE_DASHBOARD"),
    )


@recipe_library_bp.route("/recipes/library/organizations/<int:organization_id>")
def organization_marketplace(organization_id: int):
    if not is_feature_enabled("FEATURE_ORG_MARKETPLACE_DASHBOARD"):
        abort(404)

    org = Organization.query.get_or_404(organization_id)
    if org.recipe_library_blocked:
        abort(404)

    search_query = (request.args.get("search") or "").strip()
    sale_filter = (request.args.get("sale") or "any").lower()
    sort_mode = (request.args.get("sort") or "newest").lower()

    query = (
        Recipe.query.options(
            joinedload(Recipe.product_category),
            joinedload(Recipe.product_group),
            joinedload(Recipe.stats),
        )
        .filter(
            Recipe.organization_id == org.id,
            Recipe.is_public.is_(True),
            Recipe.status == "published",
            Recipe.marketplace_status == "listed",
            Recipe.marketplace_blocked.is_(False),
        )
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
                    Recipe.marketplace_notes.ilike(like_expr),
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
        purchase_enabled=is_feature_enabled("FEATURE_RECIPE_PURCHASE_OPTIONS"),
        search_query=search_query,
        sale_filter=sale_filter,
        sort_mode=sort_mode,
    )


def _serialize_recipe_for_public(recipe: Recipe, cost_rollup: dict | None = None) -> dict:
    stats = recipe.stats[0] if getattr(recipe, "stats", None) else None
    cover_url = None
    if recipe.cover_image_path:
        cover_url = url_for("static", filename=recipe.cover_image_path)
    elif recipe.cover_image_url:
        cover_url = recipe.cover_image_url

    yield_per_dollar = None
    if stats and stats.avg_cost_per_batch and stats.avg_cost_per_batch > 0 and recipe.predicted_yield:
        yield_per_dollar = float(recipe.predicted_yield or 0) / float(stats.avg_cost_per_batch)

    ingredient_cost = None
    total_cost = None
    if cost_rollup:
        ingredient_cost = cost_rollup.get("ingredient_cost")
        total_cost = cost_rollup.get("total_cost")

    return {
        "id": recipe.id,
        "slug": slugify_value(recipe.name),
        "name": recipe.name,
        "product_group": recipe.product_group.name if recipe.product_group else None,
        "category": recipe.product_category.name if recipe.product_category else None,
        "is_for_sale": recipe.is_for_sale,
        "sale_price": float(recipe.sale_price) if recipe.sale_price is not None else None,
        "shopify_product_url": recipe.shopify_product_url,
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
        "origin": {
            "type": recipe.org_origin_type,
            "purchased": recipe.org_origin_purchased,
            "source_org_id": recipe.org_origin_source_org_id,
            "source_org_name": recipe.origin_source_org.name
            if recipe.origin_source_org
            else None,
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
