from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from wtforms.validators import ValidationError

from app.extensions import db
from app.models import InventoryItem, Recipe
from app.models.batch import Batch
from app.models.product_category import ProductCategory
from app.services.recipe_proportionality_service import RecipeProportionalityService
from app.services.recipe_service import (
    create_recipe,
    duplicate_recipe,
    get_recipe_details,
    update_recipe,
)
from app.utils.permissions import get_effective_organization_id, require_permission
from app.utils.seo import slugify_value
from app.utils.timezone_utils import TimezoneUtils

from .. import recipes_bp
from ..form_utils import (
    build_draft_prompt,
    build_prefill_from_form,
    build_recipe_submission,
    create_variation_template,
    get_recipe_form_data,
    get_submission_status,
    parse_service_error,
    recipe_from_form,
    render_recipe_form,
    safe_int,
    serialize_assoc_rows,
    serialize_prefill_rows,
)

logger = logging.getLogger(__name__)


def _resolve_active_org_id():
    org_id = get_effective_organization_id()
    if org_id:
        return org_id
    try:
        return getattr(current_user, 'organization_id', None)
    except Exception:
        return None


def _ensure_variation_has_changes(parent_recipe, variation_ingredients):
    if RecipeProportionalityService.are_recipes_proportionally_identical(
        variation_ingredients,
        parent_recipe.recipe_ingredients,
    ):
        raise ValidationError(
            "A variation must have at least one change to an ingredient or proportion. No changes were detected."
        )


def _enforce_anti_plagiarism(ingredients, *, skip_check: bool):
    if skip_check or not ingredients:
        return

    org_id = _resolve_active_org_id()
    if not org_id:
        return

    purchased_recipes = (
        Recipe.query.options(joinedload(Recipe.recipe_ingredients))
        .filter(
            Recipe.organization_id == org_id,
            Recipe.org_origin_purchased.is_(True),
        )
        .all()
    )

    for purchased in purchased_recipes:
        if RecipeProportionalityService.are_recipes_proportionally_identical(
            ingredients,
            purchased.recipe_ingredients,
        ):
            raise ValidationError(
                "This recipe is identical to a recipe you have purchased. Please create a variation of your purchased recipe instead."
            )


@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.create')
def new_recipe():
    if request.method == 'POST':
        is_clone = request.form.get('is_clone') == 'true'
        cloned_from_id = safe_int(request.form.get('cloned_from_id'))
        target_status = get_submission_status(request.form)
        try:
            submission = build_recipe_submission(request.form, request.files)
            if not submission.ok:
                flash(submission.error, 'error')
                ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
                form_recipe = recipe_from_form(request.form)
                return render_recipe_form(
                    recipe=form_recipe,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    is_clone=is_clone,
                    cloned_from_id=cloned_from_id,
                    form_values=request.form,
                )

            payload = dict(submission.kwargs)
            payload.update(
                {
                    'status': target_status,
                    'cloned_from_id': cloned_from_id,
                }
            )

            submitted_ingredients = payload.get('ingredients') or []

            try:
                _enforce_anti_plagiarism(
                    submitted_ingredients,
                    skip_check=bool(cloned_from_id),
                )
            except ValidationError as exc:
                flash(str(exc), 'error')
                ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
                form_recipe = recipe_from_form(request.form)
                return render_recipe_form(
                    recipe=form_recipe,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    is_clone=is_clone,
                    cloned_from_id=cloned_from_id,
                    form_values=request.form,
                )

            success, result = create_recipe(**payload)

            if success:
                try:
                    created_names = []
                    for ing in submitted_ingredients:
                        item = db.session.get(InventoryItem, ing['item_id'])
                        if (
                            item
                            and not getattr(item, 'global_item_id', None)
                            and float(getattr(item, 'quantity', 0) or 0) == 0.0
                        ):
                            created_names.append(item.name)
                    if created_names:
                        flash(
                            "Added {} new inventory item(s) from this recipe: {}".format(
                                len(created_names), ", ".join(created_names)
                            )
                        )
                except Exception:
                    pass
                if target_status == 'draft':
                    flash(
                        'Recipe saved as a draft. You can finish it later from the recipes list.',
                        'info',
                    )
                else:
                    flash('Recipe published successfully.', 'success')
                try:
                    from flask import session as _session

                    _session.pop('tool_draft', None)
                    _session.pop('tool_draft_meta', None)
                except Exception:
                    pass
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))

            error_message, missing_fields = parse_service_error(result)
            draft_prompt = build_draft_prompt(missing_fields, target_status, error_message)
            flash(f'Error creating recipe: {error_message}', 'error')
            ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
            form_recipe = recipe_from_form(request.form)
            return render_recipe_form(
                recipe=form_recipe,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                is_clone=is_clone,
                cloned_from_id=cloned_from_id,
                form_values=request.form,
                draft_prompt=draft_prompt,
            )

        except Exception as exc:
            db.session.rollback()
            logger.exception("Error creating recipe: %s", exc)
            flash('An unexpected error occurred', 'error')
            ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
            form_recipe = recipe_from_form(request.form)
            return render_recipe_form(
                recipe=form_recipe,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                is_clone=is_clone,
                cloned_from_id=cloned_from_id,
                form_values=request.form,
            )

    from flask import session

    draft = session.get('tool_draft', None)
    try:
        meta = session.get('tool_draft_meta') or {}
        created_at = meta.get('created_at')
        if created_at:
            created_dt = datetime.fromisoformat(created_at)
            created_dt = TimezoneUtils.ensure_timezone_aware(created_dt)
            if datetime.now(timezone.utc) - created_dt > timedelta(hours=72):
                session.pop('tool_draft', None)
                session.pop('tool_draft_meta', None)
                draft = None
    except Exception:
        pass
    prefill = None
    if isinstance(draft, dict):
        try:
            prefill = Recipe(
                name=draft.get('name') or '',
                instructions=draft.get('instructions') or '',
                predicted_yield=float(draft.get('predicted_yield') or 0) or 0.0,
                predicted_yield_unit=(draft.get('predicted_yield_unit') or ''),
            )
            cat_name = (draft.get('category_name') or '').strip()
            if cat_name:
                cat = (
                    ProductCategory.query.filter(
                        func.lower(ProductCategory.name) == func.lower(db.literal(cat_name))
                    ).first()
                )
                if cat:
                    prefill.category_id = cat.id
        except Exception:
            prefill = None

    return render_recipe_form(recipe=prefill)


@recipes_bp.route('/<int:recipe_id>/variation', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.create_variations')
def create_variation(recipe_id):
    try:
        parent = get_recipe_details(recipe_id)
        if not parent:
            flash('Parent recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))
        if not parent.is_master or parent.test_sequence is not None:
            flash('Variations can only be created from a published master recipe.', 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

        if request.method == 'POST':
            target_status = get_submission_status(request.form)
            submission = build_recipe_submission(
                request.form, request.files, defaults=parent
            )
            if not submission.ok:
                flash(submission.error, 'error')
                ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
                variation_draft = recipe_from_form(request.form, base_recipe=parent)
                variation_draft.parent_recipe_id = parent.id
                return render_recipe_form(
                    recipe=variation_draft,
                    is_variation=True,
                    parent_recipe=parent,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form,
                )

            payload = dict(submission.kwargs)
            payload.update(
                {
                    'parent_recipe_id': parent.id,
                    'status': target_status,
                }
            )
            
            if not payload.get('label_prefix') and parent.label_prefix:
                payload['label_prefix'] = ""

            try:
                _ensure_variation_has_changes(parent, payload.get('ingredients') or [])
            except ValidationError as exc:
                flash(str(exc), 'error')
                ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
                variation_draft = recipe_from_form(request.form, base_recipe=parent)
                variation_draft.parent_recipe_id = parent.id
                return render_recipe_form(
                    recipe=variation_draft,
                    is_variation=True,
                    parent_recipe=parent,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form,
                )

            if parent.org_origin_purchased:
                payload['is_sellable'] = True
            elif getattr(parent, 'is_sellable', True) is False:
                payload['is_sellable'] = False

            success, result = create_recipe(**payload)

            if success:
                if target_status == 'draft':
                    flash('Variation saved as a draft.', 'info')
                else:
                    flash('Recipe variation created successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))

            error_message, missing_fields = parse_service_error(result)
            draft_prompt = build_draft_prompt(missing_fields, target_status, error_message)
            flash(f'Error creating variation: {error_message}', 'error')
            ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
            variation_draft = recipe_from_form(request.form, base_recipe=parent)
            variation_draft.parent_recipe_id = parent.id
            return render_recipe_form(
                recipe=variation_draft,
                is_variation=True,
                parent_recipe=parent,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                form_values=request.form,
                draft_prompt=draft_prompt,
            )

        new_variation = create_variation_template(parent)
        requested_name = (request.args.get('variation_name') or '').strip()
        if requested_name:
            new_variation.name = f"{parent.name} - {requested_name}"
        ingredient_prefill = serialize_assoc_rows(parent.recipe_ingredients)
        consumable_prefill = serialize_assoc_rows(parent.recipe_consumables)

        return render_recipe_form(
            recipe=new_variation,
            is_variation=True,
            parent_recipe=parent,
            ingredient_prefill=ingredient_prefill,
            consumable_prefill=consumable_prefill,
        )

    except Exception as exc:
        flash(f"Error creating variation: {exc}", "error")
        logger.exception("Error creating variation: %s", exc)
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/test', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.create')
def create_test_version(recipe_id):
    try:
        base = get_recipe_details(recipe_id)
        if not base:
            flash('Recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))
        if base.status != 'published':
            flash('Publish the recipe before creating tests.', 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

        if request.method == 'POST':
            submission = build_recipe_submission(request.form, request.files, defaults=base)
            if not submission.ok:
                flash(submission.error, 'error')
                ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
                test_draft = recipe_from_form(request.form, base_recipe=base)
                return render_recipe_form(
                    recipe=test_draft,
                    is_test=True,
                    test_base_id=base.id,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form,
                )

            payload = dict(submission.kwargs)
            payload.update(
                {
                    'status': 'published',
                    'is_test': True,
                    'recipe_group_id': base.recipe_group_id,
                    'variation_name': base.variation_name,
                    'parent_master_id': base.parent_master_id,
                    'parent_recipe_id': base.parent_recipe_id,
                    'version_number_override': base.version_number,
                }
            )

            success, result = create_recipe(**payload)
            if success:
                flash('Test version created successfully.', 'success')
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))

            error_message, missing_fields = parse_service_error(result)
            draft_prompt = build_draft_prompt(missing_fields, 'published', error_message)
            flash(f'Error creating test: {error_message}', 'error')
            ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
            test_draft = recipe_from_form(request.form, base_recipe=base)
            return render_recipe_form(
                recipe=test_draft,
                is_test=True,
                test_base_id=base.id,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                form_values=request.form,
                draft_prompt=draft_prompt,
            )

        test_template = Recipe(
            name=base.name,
            instructions=base.instructions,
            label_prefix=base.label_prefix,
            predicted_yield=base.predicted_yield,
            predicted_yield_unit=base.predicted_yield_unit,
            category_id=base.category_id,
        )
        test_template.recipe_group_id = base.recipe_group_id
        test_template.is_master = base.is_master
        test_template.variation_name = base.variation_name
        test_template.variation_prefix = base.variation_prefix
        test_template.parent_recipe_id = base.parent_recipe_id
        test_template.parent_master_id = base.parent_master_id
        test_template.portioning_data = (
            base.portioning_data.copy() if isinstance(base.portioning_data, dict) else base.portioning_data
        )
        test_template.is_portioned = base.is_portioned
        test_template.portion_name = base.portion_name
        test_template.portion_count = base.portion_count
        test_template.portion_unit_id = base.portion_unit_id
        if base.category_data:
            test_template.category_data = (
                base.category_data.copy() if isinstance(base.category_data, dict) else base.category_data
            )
        test_template.skin_opt_in = base.skin_opt_in
        test_template.sharing_scope = 'private'
        test_template.is_public = False
        test_template.is_for_sale = False

        ingredient_prefill = serialize_assoc_rows(base.recipe_ingredients)
        consumable_prefill = serialize_assoc_rows(base.recipe_consumables)

        return render_recipe_form(
            recipe=test_template,
            is_test=True,
            test_base_id=base.id,
            ingredient_prefill=ingredient_prefill,
            consumable_prefill=consumable_prefill,
        )

    except Exception as exc:
        flash(f"Error creating test: {exc}", "error")
        logger.exception("Error creating test: %s", exc)
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.edit')
def edit_recipe(recipe_id):
    recipe = get_recipe_details(recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    existing_batches = Batch.query.filter_by(recipe_id=recipe.id).count()
    if recipe.is_locked:
        flash('This recipe is locked and cannot be edited.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
    if recipe.status == 'published' and recipe.test_sequence is None:
        flash('Published versions are locked. Create a test to make edits.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
    if recipe.test_sequence is not None and existing_batches > 0:
        flash('Tests cannot be edited after running batches.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

    draft_prompt = None
    form_override = None
    if request.method == 'POST':
        target_status = get_submission_status(request.form)
        try:
            submission = build_recipe_submission(
                request.form, request.files, defaults=recipe, existing=recipe
            )
            if not submission.ok:
                flash(submission.error, 'error')
                form_override = request.form
                ingredient_prefill, consumable_prefill = build_prefill_from_form(request.form)
                return render_recipe_form(
                    recipe=recipe,
                    edit_mode=True,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=form_override,
                )

            payload = dict(submission.kwargs)
            payload['status'] = target_status

            success, result = update_recipe(
                recipe_id=recipe_id,
                **payload,
            )

            if success:
                if target_status == 'draft':
                    flash('Recipe saved as a draft.', 'info')
                else:
                    flash('Recipe updated successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
            else:
                error_message, missing_fields = parse_service_error(result)
                draft_prompt = build_draft_prompt(missing_fields, target_status, error_message)
                form_override = request.form
                flash(f'Error updating recipe: {error_message}', 'error')

        except Exception as exc:
            logger.exception("Error updating recipe: %s", exc)
            flash('An unexpected error occurred', 'error')

    form_data = get_recipe_form_data()

    return render_template(
        'pages/recipes/recipe_form.html',
        recipe=recipe,
        edit_mode=True,
        is_test=bool(recipe.test_sequence),
        existing_batches=existing_batches,
        draft_prompt=draft_prompt,
        form_values=form_override,
        **form_data,
    )


@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
@require_permission('recipes.create')
def clone_recipe(recipe_id):
    try:
        flash("Cloning recipes has been retired. Use Create New Version instead.", "warning")

    except Exception as exc:
        db.session.rollback()
        flash(f"Error handling clone request: {exc}", "error")
        logger.exception("Error cloning recipe: %s", exc)

    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/import', methods=['GET'])
@login_required
@require_permission('recipes.view')
def import_recipe(recipe_id: int):
    effective_org_id = get_effective_organization_id()
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe:
        flash("Recipe not found.", "error")
        return redirect(url_for('recipe_library_bp.recipe_library'))

    detail_url = url_for(
        'recipe_library_bp.recipe_library_detail',
        recipe_id=recipe.id,
        slug=slugify_value(recipe.name),
    )

    if not effective_org_id:
        flash("Select an organization before importing a recipe.", "error")
        return redirect(detail_url)

    if (
        not recipe.is_public
        or recipe.status != 'published'
        or recipe.test_sequence is not None
        or recipe.marketplace_status != 'listed'
        or recipe.marketplace_blocked
    ):
        flash("This recipe is not available for import right now.", "error")
        return redirect(detail_url)

    try:
        success, payload = duplicate_recipe(
            recipe_id,
            allow_cross_org=True,
            target_org_id=effective_org_id,
        )
    except PermissionError as exc:
        logger.warning("Import blocked for recipe %s: %s", recipe_id, exc)
        flash("You do not have permission to import this recipe.", "error")
        return redirect(detail_url)

    if not success:
        flash(f"Error importing recipe: {payload}", "error")
        return redirect(detail_url)

    template_recipe = payload['template']
    ingredient_prefill = serialize_prefill_rows(payload['ingredients'])
    consumable_prefill = serialize_prefill_rows(payload['consumables'])

    if recipe.is_for_sale:
        flash("Confirm your purchase before importing paid recipes.", "warning")
    else:
        flash(
            "Review the imported recipe and click Save to add it to your workspace.",
            "info",
        )

    return render_recipe_form(
        recipe=template_recipe,
        is_clone=True,
        ingredient_prefill=ingredient_prefill,
        consumable_prefill=consumable_prefill,
        cloned_from_id=payload.get('cloned_from_id'),
        form_values=None,
        is_import=True,
    )
