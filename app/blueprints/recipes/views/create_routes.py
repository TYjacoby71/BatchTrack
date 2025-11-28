from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import InventoryItem, Recipe
from app.models.product_category import ProductCategory
from app.services.recipe_service import (
    create_recipe,
    duplicate_recipe,
    get_recipe_details,
    update_recipe,
)
from app.utils.permissions import get_effective_organization_id
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


@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
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
def create_variation(recipe_id):
    try:
        parent = get_recipe_details(recipe_id)
        if not parent:
            flash('Parent recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

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
            if payload.get('product_group_id') is None and parent.product_group_id:
                payload['product_group_id'] = parent.product_group_id
            if not payload.get('label_prefix') and parent.label_prefix:
                payload['label_prefix'] = ""

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


@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = get_recipe_details(recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    if recipe.is_locked:
        flash('This recipe is locked and cannot be edited.', 'error')
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
    from ...models import Batch

    existing_batches = Batch.query.filter_by(recipe_id=recipe.id).count()

    return render_template(
        'pages/recipes/recipe_form.html',
        recipe=recipe,
        edit_mode=True,
        existing_batches=existing_batches,
        draft_prompt=draft_prompt,
        form_values=form_override,
        **form_data,
    )


@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    try:
        success, payload = duplicate_recipe(recipe_id)

        if success:
            template_recipe = payload['template']
            ingredient_prefill = serialize_prefill_rows(payload['ingredients'])
            consumable_prefill = serialize_prefill_rows(payload['consumables'])

            return render_recipe_form(
                recipe=template_recipe,
                is_clone=True,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                cloned_from_id=payload.get('cloned_from_id'),
                form_values=None,
            )
        else:
            flash(f"Error cloning recipe: {payload}", "error")

    except Exception as exc:
        db.session.rollback()
        flash(f"Error cloning recipe: {exc}", "error")
        logger.exception("Error cloning recipe: %s", exc)

    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/import', methods=['GET'])
@login_required
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

    if not recipe.is_public or recipe.marketplace_status != 'listed' or recipe.marketplace_blocked:
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
