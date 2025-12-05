from __future__ import annotations

import logging

from flask import flash, redirect, request, url_for, render_template, current_app
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app.extensions import db, cache
from app.models import Recipe, RecipeLineage
from app.services.recipe_service import delete_recipe, get_recipe_details
from app.services.cache_invalidation import (
    recipe_list_cache_key,
    recipe_list_page_cache_key,
)
from app.utils.cache_utils import should_bypass_cache
from app.utils.unit_utils import get_global_unit_list

from .. import recipes_bp

logger = logging.getLogger(__name__)

class _LengthProxy:
    __slots__ = ("_count",)

    def __init__(self, count: int):
        self._count = int(count or 0)

    def __len__(self) -> int:
        return self._count

    def __bool__(self) -> bool:
        return self._count > 0

    def __iter__(self):
        return iter(())


class _RecipeVariationView:
    __slots__ = ("id", "name", "label_prefix", "status")

    def __init__(self, data: dict):
        self.id = data.get("id")
        self.name = data.get("name")
        self.label_prefix = data.get("label_prefix")
        self.status = data.get("status")


class _RecipeListViewModel:
    __slots__ = (
        "id",
        "name",
        "label_prefix",
        "status",
        "org_origin_purchased",
        "recipe_ingredients",
        "predicted_yield",
        "predicted_yield_unit",
        "instructions",
        "batches",
        "variations",
        "requires_containers",
        "parent_recipe_id",
    )

    def __init__(self, data: dict):
        self.id = data.get("id")
        self.name = data.get("name")
        self.label_prefix = data.get("label_prefix")
        self.status = data.get("status")
        self.org_origin_purchased = data.get("org_origin_purchased", False)
        self.predicted_yield = data.get("predicted_yield")
        self.predicted_yield_unit = data.get("predicted_yield_unit")
        self.instructions = data.get("instructions")
        self.requires_containers = data.get("requires_containers", False)
        self.parent_recipe_id = data.get("parent_recipe_id")
        self.recipe_ingredients = _LengthProxy(data.get("recipe_ingredients_count", 0))
        self.batches = _LengthProxy(data.get("batches_count", 0))
        self.variations = [_RecipeVariationView(item) for item in data.get("variations", [])]


def _serialize_recipe_for_cache(recipe: Recipe) -> dict:
    variations = getattr(recipe, "variations", []) or []
    serialized_variations = [
        {
            "id": variation.id,
            "name": variation.name,
            "label_prefix": getattr(variation, "label_prefix", None),
            "status": getattr(variation, "status", None),
        }
        for variation in variations
    ]

    ingredients_count = len(getattr(recipe, "recipe_ingredients", []) or [])
    batches_count = len(getattr(recipe, "batches", []) or [])

    predicted_yield = getattr(recipe, "predicted_yield", None)
    if predicted_yield is not None:
        try:
            predicted_yield = float(predicted_yield)
        except (TypeError, ValueError):
            predicted_yield = None

    return {
        "id": recipe.id,
        "name": recipe.name,
        "label_prefix": getattr(recipe, "label_prefix", None),
        "status": getattr(recipe, "status", None),
        "org_origin_purchased": bool(getattr(recipe, "org_origin_purchased", False)),
        "instructions": getattr(recipe, "instructions", None),
        "predicted_yield": predicted_yield,
        "predicted_yield_unit": getattr(recipe, "predicted_yield_unit", None),
        "requires_containers": bool(getattr(recipe, "requires_containers", False)),
        "parent_recipe_id": getattr(recipe, "parent_recipe_id", None),
        "recipe_ingredients_count": ingredients_count,
        "batches_count": batches_count,
        "variations": serialized_variations,
    }


def _hydrate_recipe_from_cache(data: dict) -> _RecipeListViewModel:
    return _RecipeListViewModel(data)


@recipes_bp.route('/')
@login_required
def list_recipes():
    org_id = getattr(current_user, "organization_id", None) or 0
    cache_key = recipe_list_cache_key(org_id)
    page_cache_key = recipe_list_page_cache_key(org_id)
    bypass_cache = should_bypass_cache()
    cache_ttl = current_app.config.get("RECIPE_LIST_CACHE_TTL", 180)

    if bypass_cache:
        cache.delete(cache_key)
        cache.delete(page_cache_key)
    else:
        cached_page = cache.get(page_cache_key)
        if cached_page is not None:
            return cached_page
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            recipes = [_hydrate_recipe_from_cache(entry) for entry in cached_payload]
            inventory_units = get_global_unit_list()
            rendered = render_template(
                'pages/recipes/recipe_list.html',
                recipes=recipes,
                inventory_units=inventory_units,
            )
            try:
                cache.set(page_cache_key, rendered, timeout=cache_ttl)
            except Exception:
                pass
            return rendered

    query = Recipe.query.filter_by(parent_recipe_id=None)
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)

    recipes = (
        query.options(
            selectinload(Recipe.variations),
            selectinload(Recipe.recipe_ingredients),
            selectinload(Recipe.batches),
        )
        .order_by(Recipe.name.asc())
        .all()
    )

    serialized = [_serialize_recipe_for_cache(recipe) for recipe in recipes]
    cache.set(
        cache_key,
        serialized,
        timeout=cache_ttl,
    )
    recipes = [_hydrate_recipe_from_cache(entry) for entry in serialized]
    inventory_units = get_global_unit_list()
    rendered = render_template(
        'pages/recipes/recipe_list.html',
        recipes=recipes,
        inventory_units=inventory_units,
    )
    try:
        cache.set(page_cache_key, rendered, timeout=cache_ttl)
    except Exception:
        pass
    return rendered


@recipes_bp.route('/<int:recipe_id>/view')
@login_required
def view_recipe(recipe_id):
    try:
        recipe = get_recipe_details(recipe_id)
        if not recipe:
            flash('Recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        inventory_units = get_global_unit_list()
        lineage_enabled = True
        return render_template(
            'pages/recipes/view_recipe.html',
            recipe=recipe,
            inventory_units=inventory_units,
            lineage_enabled=lineage_enabled,
        )

    except Exception as exc:
        flash(f"Error loading recipe: {exc}", "error")
        logger.exception("Error viewing recipe: %s", exc)
        return redirect(url_for('recipes.list_recipes'))


@recipes_bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
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
def lock_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.is_locked = True
    db.session.commit()
    flash('Recipe locked successfully.')
    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/unlock', methods=['POST'])
@login_required
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
