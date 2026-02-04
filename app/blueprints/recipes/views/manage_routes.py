from __future__ import annotations

import logging

from flask import flash, redirect, request, url_for, render_template, current_app
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app.extensions import db, cache
from app.models import Recipe, RecipeLineage
from app.services.recipe_service import delete_recipe, get_recipe_details
from app.services.cache_invalidation import recipe_list_page_cache_key
from app.utils.cache_utils import should_bypass_cache
from app.utils.permissions import _org_tier_includes_permission, has_permission, require_permission
from app.utils.unit_utils import get_global_unit_list
from app.utils.settings import is_feature_enabled

from .. import recipes_bp

logger = logging.getLogger(__name__)

@recipes_bp.route('/')
@login_required
@require_permission('recipes.view')
def list_recipes():
    org_id = getattr(current_user, "organization_id", None) or 0
    bypass_cache = should_bypass_cache()
    cache_ttl = current_app.config.get("RECIPE_LIST_CACHE_TTL", 180)
    try:
        per_page = int(current_app.config.get("RECIPE_LIST_PAGE_SIZE", 10))
    except (TypeError, ValueError):
        per_page = 10
    per_page = max(1, min(per_page, 100))
    page = request.args.get("page", 1, type=int) or 1
    if page < 1:
        page = 1
    page_cache_key = recipe_list_page_cache_key(org_id, page=page)

    if bypass_cache:
        cache.delete(page_cache_key)
    else:
        cached_page = cache.get(page_cache_key)
        if cached_page is not None:
            return cached_page

    query = Recipe.query.filter_by(parent_recipe_id=None)
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)

    pagination = (
        query.options(
            selectinload(Recipe.variations),
            selectinload(Recipe.recipe_ingredients),
            selectinload(Recipe.batches),
        )
        .order_by(Recipe.name.asc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    if pagination.pages and page > pagination.pages:
        return redirect(url_for('recipes.list_recipes', page=pagination.pages))
    recipes = pagination.items
    inventory_units = get_global_unit_list()
    rendered = render_template(
        'pages/recipes/recipe_list.html',
        recipes=recipes,
        inventory_units=inventory_units,
        pagination=pagination,
    )
    try:
        cache.set(page_cache_key, rendered, timeout=cache_ttl)
    except Exception:
        pass
    return rendered


@recipes_bp.route('/<int:recipe_id>/view')
@login_required
@require_permission('recipes.view')
def view_recipe(recipe_id):
    try:
        recipe = get_recipe_details(recipe_id)
        if not recipe:
            flash('Recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        inventory_units = get_global_unit_list()
        lineage_enabled = True
        origin_marketplace_enabled = False
        if recipe.org_origin_source_org:
            origin_marketplace_enabled = _org_tier_includes_permission(
                recipe.org_origin_source_org, "recipes.marketplace_dashboard"
            )
        show_origin_marketplace = (
            is_feature_enabled("FEATURE_RECIPE_MARKETPLACE_DISPLAY")
            and origin_marketplace_enabled
            and has_permission(current_user, "recipes.marketplace_dashboard")
        )
        return render_template(
            'pages/recipes/view_recipe.html',
            recipe=recipe,
            inventory_units=inventory_units,
            lineage_enabled=lineage_enabled,
            show_origin_marketplace=show_origin_marketplace,
        )

    except Exception as exc:
        flash(f"Error loading recipe: {exc}", "error")
        logger.exception("Error viewing recipe: %s", exc)
        return redirect(url_for('recipes.list_recipes'))


@recipes_bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
@require_permission('recipes.delete')
def delete_recipe_route(recipe_id):
    try:
        success, message = delete_recipe(recipe_id)
        if success:
            flash(message)
        else:
            flash(f'Error deleting recipe: {message}', 'error')
    except Exception as exc:
        logger.error("Error deleting recipe %s: %s", recipe_id, exc)
        flash('An error occurred while deleting the recipe.', 'error')

    return redirect(url_for('recipes.list_recipes'))


@recipes_bp.route('/<int:recipe_id>/make-parent', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def make_parent_recipe(recipe_id):
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            flash('Recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        if not recipe.parent_recipe_id:
            flash('Recipe is already a parent recipe.', 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

        original_parent = recipe.parent

        recipe.parent_recipe_id = None

        if recipe.name.endswith(" Variation"):
            recipe.name = recipe.name.replace(" Variation", "")

        lineage_entry = RecipeLineage(
            recipe_id=recipe.id,
            source_recipe_id=original_parent.id if original_parent else None,
            event_type='PROMOTE_TO_PARENT',
            organization_id=recipe.organization_id,
            user_id=getattr(current_user, 'id', None),
        )
        db.session.add(lineage_entry)

        db.session.commit()

        flash(
            f'Recipe "{recipe.name}" has been converted to a parent recipe and is no longer '
            f'a variation of "{original_parent.name}".',
            'success',
        )
        logger.info("Converted recipe %s from variation to parent recipe", recipe_id)

        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

    except Exception as exc:
        db.session.rollback()
        logger.error("Error converting recipe %s to parent: %s", recipe_id, exc)
        flash('An error occurred while converting the recipe to a parent.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/lock', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def lock_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.is_locked = True
    db.session.commit()
    flash('Recipe locked successfully.')
    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/unlock', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def unlock_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    unlock_password = request.form.get('unlock_password')

    if current_user.check_password(unlock_password):
        recipe.is_locked = False
        db.session.commit()
        flash('Recipe unlocked successfully.')
    else:
        flash('Incorrect password.', 'error')

    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
