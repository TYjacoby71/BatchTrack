"""Recipe management routes.

Synopsis:
Lists recipes, shows lineage view, captures recipe notes, and provides promotion/archive actions.

Glossary:
- Lineage: Versioned recipe history within a group.
- Promotion: Converting tests or variations to current/master.
"""

from __future__ import annotations

import logging


from flask import flash, redirect, request, url_for, render_template, current_app
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import selectinload
 
from app.extensions import db, cache
from app.models import Recipe, RecipeIngredient, RecipeLineage, Batch
from app.services.lineage_service import format_label_prefix, generate_lineage_id
from app.services.recipe_service import (
    archive_recipe,
    delete_recipe,
    get_recipe_details,
    is_marketplace_listed,
    set_current_version as set_current_version_service,
    promote_test_to_current,
    promote_variation_to_master as promote_variation_to_master_service,
    promote_variation_to_new_group as promote_variation_to_new_group_service,
    restore_recipe,
    unlist_recipe,
)
from app.services.cache_invalidation import recipe_list_page_cache_key
from app.utils.cache_utils import should_bypass_cache
from app.utils.notes import append_timestamped_note
from app.utils.permissions import _org_tier_includes_permission, has_permission, require_permission
from app.utils.unit_utils import get_global_unit_list
from app.utils.settings import is_feature_enabled
from ..lineage_utils import build_version_branches

from .. import recipes_bp

logger = logging.getLogger(__name__)


# --- Group variations for masters ---
# Purpose: Fetch group-scoped non-test variations for listed master rows.
# Inputs: Master recipe rows and optional organization scope identifier.
# Outputs: Mapping of recipe_group_id to variation Recipe rows.
def _group_variations_for_masters(recipes, *, organization_id: int | None) -> dict[int, list[Recipe]]:
    """Return non-test, non-archived variations bucketed by recipe group."""
    group_ids = sorted(
        {
            int(recipe.recipe_group_id)
            for recipe in recipes
            if getattr(recipe, "recipe_group_id", None)
        }
    )
    if not group_ids:
        return {}

    query = Recipe.query.filter(
        Recipe.recipe_group_id.in_(group_ids),
        Recipe.is_master.is_(False),
        Recipe.test_sequence.is_(None),
        Recipe.is_archived.is_(False),
    )
    if organization_id:
        query = query.filter(Recipe.organization_id == organization_id)

    grouped: dict[int, list[Recipe]] = {}
    for variation in (
        query.order_by(
            Recipe.recipe_group_id.asc(),
            Recipe.variation_name.asc().nullsfirst(),
            Recipe.version_number.desc(),
        ).all()
    ):
        grouped.setdefault(int(variation.recipe_group_id), []).append(variation)
    return grouped

# =========================================================
# LISTING & VIEW
# =========================================================
# --- List recipes ---
# Purpose: List master recipes for the organization.
# Inputs: Request query args for pagination plus authenticated organization scope.
# Outputs: Rendered recipe list HTML response with group-aware variation payloads.
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

    ingredient_counts_query = (
        db.session.query(
            RecipeIngredient.recipe_id.label("recipe_id"),
            func.count(RecipeIngredient.id).label("ingredient_count"),
        )
        .group_by(RecipeIngredient.recipe_id)
    )
    batch_counts_query = (
        db.session.query(
            Batch.recipe_id.label("recipe_id"),
            func.count(Batch.id).label("batch_count"),
        )
        .group_by(Batch.recipe_id)
    )
    if current_user.organization_id:
        ingredient_counts_query = ingredient_counts_query.filter(
            RecipeIngredient.organization_id == current_user.organization_id
        )
        batch_counts_query = batch_counts_query.filter(
            Batch.organization_id == current_user.organization_id
        )

    ingredient_counts = ingredient_counts_query.subquery()
    batch_counts = batch_counts_query.subquery()

    base_filters = [
        Recipe.parent_recipe_id.is_(None),
        Recipe.test_sequence.is_(None),
        Recipe.is_archived.is_(False),
        Recipe.is_current.is_(True),
    ]
    if current_user.organization_id:
        base_filters.append(Recipe.organization_id == current_user.organization_id)

    query = (
        Recipe.query.filter(*base_filters)
        .outerjoin(ingredient_counts, ingredient_counts.c.recipe_id == Recipe.id)
        .outerjoin(batch_counts, batch_counts.c.recipe_id == Recipe.id)
        .add_columns(
            ingredient_counts.c.ingredient_count,
            batch_counts.c.batch_count,
        )
    )

    pagination = (
        query.options(
            selectinload(Recipe.variations),
        )
        .order_by(Recipe.name.asc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    if pagination.pages and page > pagination.pages:
        return redirect(url_for('recipes.list_recipes', page=pagination.pages))
    recipes = []
    for recipe, ingredient_count, batch_count in pagination.items:
        recipe.ingredient_count = int(ingredient_count or 0)
        recipe.batch_count = int(batch_count or 0)
        recipes.append(recipe)

    group_variations = _group_variations_for_masters(
        recipes,
        organization_id=getattr(current_user, "organization_id", None),
    )
    for recipe in recipes:
        fallback_variations = [
            variation
            for variation in getattr(recipe, "variations", [])
            if variation.test_sequence is None and not variation.is_archived
        ]
        recipe.group_variations = group_variations.get(recipe.recipe_group_id, fallback_variations)

    inventory_units = get_global_unit_list()
    rendered = render_template(
        'pages/recipes/recipe_list.html',
        recipes=recipes,
        inventory_units=inventory_units,
        pagination=pagination,
        breadcrumb_items=[{'label': 'Recipes'}],
    )
    try:
        cache.set(page_cache_key, rendered, timeout=cache_ttl)
    except Exception:
        pass
    return rendered


# --- View recipe ---
# Purpose: View a recipe, its lineage context, and note history.
# Inputs: Recipe id path parameter and authenticated user context.
# Outputs: Rendered recipe detail page or redirect with flash messaging.
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
        can_create_variations = has_permission(current_user, "recipes.create_variations")
        lineage_id = generate_lineage_id(recipe)
        batch_count = Batch.query.filter_by(recipe_id=recipe.id).count()
        has_batches = batch_count > 0
        if recipe.recipe_group_id:
            variation_count = Recipe.query.filter(
                Recipe.recipe_group_id == recipe.recipe_group_id,
                Recipe.is_master.is_(False),
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
            ).count()
        else:
            variation_count = Recipe.query.filter(
                Recipe.parent_recipe_id == recipe.id,
                Recipe.test_sequence.is_(None),
                Recipe.is_archived.is_(False),
                Recipe.is_current.is_(True),
            ).count()
        is_test = recipe.test_sequence is not None
        is_published_locked = recipe.status == 'published' and not is_test
        is_archived = bool(recipe.is_archived)
        can_edit = has_permission(current_user, "recipes.edit")
        lineage_enabled = can_edit
        is_editable = (
            can_edit
            and (not is_published_locked)
            and (not (is_test and has_batches))
            and (not is_archived)
        )
        force_edit_allowed = (
            can_edit
            and is_published_locked
            and (not recipe.is_locked)
            and (not is_archived)
        )
        has_listing = is_marketplace_listed(recipe)
        can_add_notes = can_edit

        note_types = ("NOTE", "EDIT", "EDIT_OVERRIDE")
        recipe_notes = (
            RecipeLineage.query.filter(
                RecipeLineage.recipe_id == recipe.id,
                RecipeLineage.notes.isnot(None),
                RecipeLineage.event_type.in_(note_types),
            )
            .order_by(RecipeLineage.created_at.desc())
            .limit(25)
            .all()
        )

        group_versions = []
        master_branches = []
        variation_branches = []
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
            master_branches, variation_branches = build_version_branches(group_versions)
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
        label_prefix_display = format_label_prefix(
            recipe,
            include_master_version_for_master=True,
        )
        origin_root_recipe = recipe.root_recipe or recipe
        origin_parent_recipe = recipe.parent
        if recipe.is_master and recipe.test_sequence is None and recipe.recipe_group_id:
            origin_parent_recipe = (
                Recipe.query.filter(
                    Recipe.recipe_group_id == recipe.recipe_group_id,
                    Recipe.is_master.is_(True),
                    Recipe.test_sequence.is_(None),
                    Recipe.version_number < recipe.version_number,
                )
                .order_by(Recipe.version_number.desc())
                .first()
            )
        return render_template(
            'pages/recipes/view_recipe.html',
            recipe=recipe,
            inventory_units=inventory_units,
            lineage_enabled=lineage_enabled,
            label_prefix_display=label_prefix_display,
            show_origin_marketplace=show_origin_marketplace,
            lineage_id=lineage_id,
            is_test=is_test,
            is_published_locked=is_published_locked,
            is_editable=is_editable,
            force_edit_allowed=force_edit_allowed,
            can_add_notes=can_add_notes,
            recipe_notes=recipe_notes,
            has_batches=has_batches,
            batch_count=batch_count,
            variation_count=variation_count,
            is_archived=is_archived,
            has_listing=has_listing,
            master_branches=master_branches,
            variation_branches=variation_branches,
            can_create_variations=can_create_variations,
            can_edit=can_edit,
            origin_root_recipe=origin_root_recipe,
            origin_parent_recipe=origin_parent_recipe,
        )

    except Exception as exc:
        flash(f"Error loading recipe: {exc}", "error")
        logger.exception("Error viewing recipe: %s", exc)
        return redirect(url_for('recipes.list_recipes'))


# --- Add recipe note ---
# Purpose: Store timestamped notes for a recipe.
# Inputs: Recipe id path parameter and submitted note body from form data.
# Outputs: Redirect response back to recipe view with success/error flash.
@recipes_bp.route('/<int:recipe_id>/notes', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def add_recipe_note(recipe_id):
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    note_text = (request.form.get('note') or '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id) + "#recipeNotes")

    try:
        stamped = append_timestamped_note(None, note_text)
        lineage_entry = RecipeLineage(
            recipe_id=recipe.id,
            event_type='NOTE',
            organization_id=recipe.organization_id,
            user_id=getattr(current_user, 'id', None),
            notes=stamped,
        )
        db.session.add(lineage_entry)
        db.session.commit()
        flash('Note added.', 'success')
    except Exception as exc:
        db.session.rollback()
        logger.error("Error adding recipe note %s: %s", recipe_id, exc)
        flash('Unable to save note.', 'error')

    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id) + "#recipeNotes")


# =========================================================
# LEGACY ACTIONS
# =========================================================
# --- Delete recipe ---
# Purpose: Legacy destructive delete for a recipe.
# Inputs: Recipe id path parameter identifying recipe to delete.
# Outputs: Redirect response to list page with deletion result flash.
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


# --- Make parent (legacy) ---
# Purpose: Legacy promote-to-parent flow (compatibility).
# Inputs: Recipe id path parameter for variation being converted.
# Outputs: Redirect response to recipe view with conversion status flash.
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


# =========================================================
# LOCKING
# =========================================================
# --- Lock recipe ---
# Purpose: Lock a recipe to prevent edits.
# Inputs: Recipe id path parameter to lock.
# Outputs: Redirect response to recipe view after lock persistence.
@recipes_bp.route('/<int:recipe_id>/lock', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def lock_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.is_locked = True
    db.session.commit()
    flash('Recipe locked successfully.')
    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


# --- Unlock recipe ---
# Purpose: Unlock a recipe for edits.
# Inputs: Recipe id path parameter plus unlock password form value.
# Outputs: Redirect response to recipe view with unlock validation flash.
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


# =========================================================
# PROMOTIONS
# =========================================================
# --- Publish test ---
# Purpose: Promote a test to current version.
# Inputs: Test recipe id path parameter for promotion target.
# Outputs: Redirect response to promoted version or source recipe on error.
@recipes_bp.route('/<int:recipe_id>/publish-test', methods=['POST'])
@login_required
@require_permission('recipes.create_variations')
def publish_test_version(recipe_id):
    try:
        success, result = promote_test_to_current(recipe_id)
        if not success:
            flash(str(result), 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
        flash('Test promoted to current version.', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
    except Exception as exc:
        db.session.rollback()
        logger.error("Error publishing test version %s: %s", recipe_id, exc)
        flash('An error occurred while publishing the test.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


# --- Set current version ---
# Purpose: Make a published version the current recipe.
# Inputs: Published recipe id path parameter for target branch.
# Outputs: Redirect response to selected version with status flash.
@recipes_bp.route('/<int:recipe_id>/set-current', methods=['POST'])
@login_required
@require_permission('recipes.create_variations')
def set_current_version_route(recipe_id):
    try:
        success, result = set_current_version_service(recipe_id)
        if not success:
            flash(str(result), 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
        flash('Version set as current.', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
    except Exception as exc:
        db.session.rollback()
        logger.error("Error setting current version %s: %s", recipe_id, exc)
        flash('An error occurred while setting the current version.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


# --- Promote to master ---
# Purpose: Promote a variation to master in the same group.
# Inputs: Variation recipe id path parameter.
# Outputs: Redirect response to created master or source recipe on failure.
@recipes_bp.route('/<int:recipe_id>/promote-to-master', methods=['POST'])
@login_required
@require_permission('recipes.create_variations')
def promote_variation_to_master(recipe_id):
    try:
        success, result = promote_variation_to_master_service(recipe_id)
        if not success:
            flash(str(result), 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
        flash('Variation promoted to new master version.', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
    except Exception as exc:
        db.session.rollback()
        logger.error("Error promoting variation %s to master: %s", recipe_id, exc)
        flash('An error occurred while promoting the variation.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


# --- Promote to new group ---
# Purpose: Promote a variation to a new recipe group.
# Inputs: Variation recipe id path parameter and optional group_name form value.
# Outputs: Redirect response to newly created group master or source on error.
@recipes_bp.route('/<int:recipe_id>/promote-to-new-group', methods=['POST'])
@login_required
@require_permission('recipes.create_variations')
def promote_variation_to_new_group(recipe_id):
    try:
        group_name = (request.form.get("group_name") or "").strip() or None
        success, result = promote_variation_to_new_group_service(
            recipe_id,
            group_name=group_name,
        )
        if not success:
            if isinstance(result, dict):
                flash(result.get('error') or 'Unable to create a new recipe group.', 'error')
            else:
                flash(str(result), 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

        flash('Variation promoted into a new recipe group.', 'success')
        return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
    except Exception as exc:
        db.session.rollback()
        logger.error("Error promoting variation %s to new group: %s", recipe_id, exc)
        flash('An error occurred while creating the new recipe group.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


# =========================================================
# ARCHIVE & LISTINGS
# =========================================================
# --- Archive recipe ---
# Purpose: Archive a recipe (soft-hide + lock).
# Inputs: Recipe id path parameter and optional next redirect URL query arg.
# Outputs: Redirect response to provided next path or recipe detail page.
@recipes_bp.route('/<int:recipe_id>/archive', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def archive_recipe_route(recipe_id):
    try:
        success, message = archive_recipe(recipe_id, user_id=getattr(current_user, 'id', None))
        flash(message, 'success' if success else 'error')
    except Exception as exc:
        logger.error("Error archiving recipe %s: %s", recipe_id, exc)
        flash('Unable to archive recipe.', 'error')
    return redirect(request.args.get('next') or url_for('recipes.view_recipe', recipe_id=recipe_id))


# --- Restore recipe ---
# Purpose: Restore an archived recipe.
# Inputs: Recipe id path parameter and optional next redirect URL query arg.
# Outputs: Redirect response to provided next path or recipe detail page.
@recipes_bp.route('/<int:recipe_id>/restore', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def restore_recipe_route(recipe_id):
    try:
        success, message = restore_recipe(recipe_id)
        flash(message, 'success' if success else 'error')
    except Exception as exc:
        logger.error("Error restoring recipe %s: %s", recipe_id, exc)
        flash('Unable to restore recipe.', 'error')
    return redirect(request.args.get('next') or url_for('recipes.view_recipe', recipe_id=recipe_id))


# --- Deactivate listing ---
# Purpose: Deactivate a marketplace listing for the recipe.
# Inputs: Recipe id path parameter and optional next redirect URL query arg.
# Outputs: Redirect response to provided next path or recipe detail page.
@recipes_bp.route('/<int:recipe_id>/unlist', methods=['POST'])
@login_required
@require_permission('recipes.edit')
def unlist_recipe_route(recipe_id):
    try:
        success, message = unlist_recipe(recipe_id)
        flash(message, 'success' if success else 'error')
    except Exception as exc:
        logger.error("Error unlisting recipe %s: %s", recipe_id, exc)
        flash('Unable to remove listing.', 'error')
    return redirect(request.args.get('next') or url_for('recipes.view_recipe', recipe_id=recipe_id))
