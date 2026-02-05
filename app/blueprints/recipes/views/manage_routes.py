from __future__ import annotations

import logging

import sqlalchemy as sa

from flask import flash, redirect, request, url_for, render_template, current_app
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app.extensions import db, cache
from app.models import Recipe, RecipeLineage, RecipeIngredient, RecipeConsumable, Batch
from app.services.lineage_service import generate_lineage_id
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

    query = Recipe.query.filter(
        Recipe.parent_recipe_id.is_(None),
        Recipe.test_sequence.is_(None),
    )
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
        lineage_id = generate_lineage_id(recipe)
        has_batches = Batch.query.filter_by(recipe_id=recipe.id).count() > 0
        is_test = recipe.test_sequence is not None
        is_published_locked = recipe.status == 'published' and not is_test
        is_editable = (not is_published_locked) and (not (is_test and has_batches))

        group_versions = []
        master_versions = []
        master_tests = []
        variation_versions = {}
        if recipe.recipe_group_id:
            group_versions = (
                Recipe.query.filter(Recipe.recipe_group_id == recipe.recipe_group_id)
                .order_by(
                    Recipe.is_master.desc(),
                    Recipe.variation_name.asc().nullsfirst(),
                    Recipe.version_number.desc(),
                    Recipe.test_sequence.asc().nullsfirst(),
                )
                .all()
            )
            for version in group_versions:
                if version.is_master:
                    if version.test_sequence:
                        master_tests.append(version)
                    else:
                        master_versions.append(version)
                else:
                    key = version.variation_name or version.name
                    if key not in variation_versions:
                        variation_versions[key] = {"published": [], "tests": []}
                    if version.test_sequence:
                        variation_versions[key]["tests"].append(version)
                    else:
                        variation_versions[key]["published"].append(version)
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
            lineage_id=lineage_id,
            is_test=is_test,
            is_published_locked=is_published_locked,
            is_editable=is_editable,
            has_batches=has_batches,
            master_versions=master_versions,
            master_tests=master_tests,
            variation_versions=variation_versions,
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


@recipes_bp.route('/<int:recipe_id>/publish-test', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def publish_test_version(recipe_id):
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe or recipe.test_sequence is None:
            flash('Test version not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        base_query = Recipe.query.filter(
            Recipe.recipe_group_id == recipe.recipe_group_id,
            Recipe.is_master.is_(recipe.is_master),
            Recipe.test_sequence.is_(None),
        )
        if not recipe.is_master:
            base_query = base_query.filter(Recipe.variation_name == recipe.variation_name)
        max_version = base_query.with_entities(sa.func.max(Recipe.version_number)).scalar() or 0
        recipe.version_number = int(max_version) + 1
        recipe.test_sequence = None
        recipe.status = 'published'
        db.session.commit()
        flash('Test promoted to current version.', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
    except Exception as exc:
        db.session.rollback()
        logger.error("Error publishing test version %s: %s", recipe_id, exc)
        flash('An error occurred while publishing the test.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/promote-to-master', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def promote_variation_to_master(recipe_id):
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe or recipe.is_master or recipe.test_sequence is not None:
            flash('Only published variations can be promoted to master.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        max_version = (
            Recipe.query.filter(
                Recipe.recipe_group_id == recipe.recipe_group_id,
                Recipe.is_master.is_(True),
                Recipe.test_sequence.is_(None),
            )
            .with_entities(sa.func.max(Recipe.version_number))
            .scalar()
            or 0
        )
        next_version = int(max_version) + 1

        new_master = Recipe(
            name=recipe.recipe_group.name if recipe.recipe_group else recipe.name,
            instructions=recipe.instructions,
            predicted_yield=recipe.predicted_yield,
            predicted_yield_unit=recipe.predicted_yield_unit,
            organization_id=recipe.organization_id,
            recipe_group_id=recipe.recipe_group_id,
            is_master=True,
            variation_name=None,
            variation_prefix=None,
            version_number=next_version,
            parent_master_id=None,
            test_sequence=None,
            parent_recipe_id=None,
            label_prefix=recipe.label_prefix,
            category_id=recipe.category_id,
            status='published',
        )
        new_master.allowed_containers = list(recipe.allowed_containers or [])
        new_master.portioning_data = (
            recipe.portioning_data.copy() if isinstance(recipe.portioning_data, dict) else recipe.portioning_data
        )
        new_master.is_portioned = recipe.is_portioned
        new_master.portion_name = recipe.portion_name
        new_master.portion_count = recipe.portion_count
        new_master.portion_unit_id = recipe.portion_unit_id
        if recipe.category_data:
            new_master.category_data = (
                recipe.category_data.copy() if isinstance(recipe.category_data, dict) else recipe.category_data
            )
        new_master.skin_opt_in = recipe.skin_opt_in
        new_master.sharing_scope = 'private'
        new_master.is_public = False
        new_master.is_for_sale = False

        db.session.add(new_master)
        db.session.flush()

        db.session.add(
            RecipeLineage(
                recipe_id=new_master.id,
                source_recipe_id=recipe.id,
                event_type='PROMOTE_VARIATION',
                user_id=getattr(current_user, 'id', None),
                notes=f"Promoted variation {recipe.name} to master version {next_version}.",
            )
        )

        for assoc in recipe.recipe_ingredients:
            db.session.add(
                RecipeIngredient(
                    recipe_id=new_master.id,
                    inventory_item_id=assoc.inventory_item_id,
                    quantity=assoc.quantity,
                    unit=assoc.unit,
                )
            )
        for assoc in recipe.recipe_consumables:
            db.session.add(
                RecipeConsumable(
                    recipe_id=new_master.id,
                    inventory_item_id=assoc.inventory_item_id,
                    quantity=assoc.quantity,
                    unit=assoc.unit,
                )
            )

        db.session.commit()
        flash('Variation promoted to new master version.', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=new_master.id))
    except Exception as exc:
        db.session.rollback()
        logger.error("Error promoting variation %s to master: %s", recipe_id, exc)
        flash('An error occurred while promoting the variation.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
