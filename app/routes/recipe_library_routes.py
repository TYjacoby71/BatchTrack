from __future__ import annotations

from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.models import Recipe, ProductCategory, Organization
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

    query = (
        Recipe.query.options(
            joinedload(Recipe.product_category),
            joinedload(Recipe.product_group),
            joinedload(Recipe.stats),
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
    if search_query:
        like_expr = f"%{search_query}%"
        query = query.filter(
            or_(
                Recipe.name.ilike(like_expr),
                Recipe.instructions.ilike(like_expr),
            )
        )

    recipes = (
        query.order_by(Recipe.updated_at.desc(), Recipe.name.asc()).limit(60).all()
    )

    recipe_cards = [
        _serialize_recipe_for_public(recipe) for recipe in recipes
    ]

    product_groups = (
        RecipeProductGroup.query.filter_by(is_active=True)
        .order_by(RecipeProductGroup.display_order.asc(), RecipeProductGroup.name.asc())
        .all()
    )
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    stats = AnalyticsDataService.get_recipe_library_metrics()
    purchase_enabled = is_feature_enabled("FEATURE_RECIPE_PURCHASE_OPTIONS")

    return render_template(
        "library/recipe_library.html",
        recipes=recipe_cards,
        product_groups=product_groups,
        categories=categories,
        stats=stats,
        purchase_enabled=purchase_enabled,
        search_query=search_query,
        group_filter=group_filter,
        category_filter=category_filter,
        sale_filter=sale_filter,
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

    stats = _serialize_recipe_for_public(recipe)
    purchase_enabled = is_feature_enabled("FEATURE_RECIPE_PURCHASE_OPTIONS")
    return render_template(
        "library/recipe_detail.html",
        recipe=stats,
        purchase_enabled=purchase_enabled,
    )


def _serialize_recipe_for_public(recipe: Recipe) -> dict:
    stats = recipe.stats[0] if getattr(recipe, "stats", None) else None
    cover_url = None
    if recipe.cover_image_path:
        cover_url = url_for("static", filename=recipe.cover_image_path)
    elif recipe.cover_image_url:
        cover_url = recipe.cover_image_url

    yield_per_dollar = None
    if stats and stats.avg_cost_per_batch and stats.avg_cost_per_batch > 0 and recipe.predicted_yield:
        yield_per_dollar = float(recipe.predicted_yield or 0) / float(stats.avg_cost_per_batch)

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
        "stats": stats,
        "yield_per_dollar": yield_per_dollar,
        "skin_opt_in": recipe.skin_opt_in,
        "updated_at": recipe.updated_at,
    }


def _safe_int(value):
    try:
        return int(value) if value not in (None, "", "null") else None
    except (TypeError, ValueError):
        return None
