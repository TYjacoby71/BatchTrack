from dataclasses import dataclass
from typing import Any, Dict, Optional

from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from . import recipes_bp
from app.extensions import db
from app.models import Recipe, InventoryItem, GlobalItem, RecipeLineage
from app.models.recipe_marketplace import RecipeProductGroup
from app.utils.permissions import require_permission, get_effective_organization_id
from app.utils.settings import is_feature_enabled
from app.services.recipe_marketplace_service import RecipeMarketplaceService
from app.utils.seo import slugify_value

from app.services.recipe_service import (
    create_recipe, update_recipe, delete_recipe, get_recipe_details,
    duplicate_recipe
)

from app.utils.unit_utils import get_global_unit_list
from app.services.inventory_adjustment import create_inventory_item
from app.models.unit import Unit
from app.models.product_category import ProductCategory
import logging
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload
from itertools import zip_longest

logger = logging.getLogger(__name__)
_ALLOWED_COVER_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        is_clone = request.form.get('is_clone') == 'true'
        cloned_from_id = _safe_int(request.form.get('cloned_from_id'))
        target_status = _get_submission_status(request.form)
        try:
            submission = _build_recipe_submission(request.form, request.files)
            if not submission.ok:
                flash(submission.error, 'error')
                ingredient_prefill, consumable_prefill = _build_prefill_from_form(request.form)
                form_recipe = _recipe_from_form(request.form)
                return _render_recipe_form(
                    recipe=form_recipe,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    is_clone=is_clone,
                    cloned_from_id=cloned_from_id,
                    form_values=request.form
                )

            payload = dict(submission.kwargs)
            payload.update({
                'status': target_status,
                'cloned_from_id': cloned_from_id,
            })

            submitted_ingredients = payload.get('ingredients') or []
            success, result = create_recipe(**payload)

            if success:
                try:
                    created_names = []
                    for ing in submitted_ingredients:
                        from app.models import InventoryItem as _Inv
                        item = db.session.get(_Inv, ing['item_id'])
                        if item and not getattr(item, 'global_item_id', None) and float(getattr(item, 'quantity', 0) or 0) == 0.0:
                            created_names.append(item.name)
                    if created_names:
                        flash(f"Added {len(created_names)} new inventory item(s) from this recipe: " + ", ".join(created_names))
                except Exception:
                    pass
                if target_status == 'draft':
                    flash('Recipe saved as a draft. You can finish it later from the recipes list.', 'info')
                else:
                    flash('Recipe published successfully.', 'success')
                try:
                    from flask import session as _session
                    _session.pop('tool_draft', None)
                    _session.pop('tool_draft_meta', None)
                except Exception:
                    pass
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))

            error_message, missing_fields = _parse_service_error(result)
            draft_prompt = _build_draft_prompt(missing_fields, target_status, error_message)
            flash(f'Error creating recipe: {error_message}', 'error')
            ingredient_prefill, consumable_prefill = _build_prefill_from_form(request.form)
            form_recipe = _recipe_from_form(request.form)
            return _render_recipe_form(
                recipe=form_recipe,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                is_clone=is_clone,
                cloned_from_id=cloned_from_id,
                form_values=request.form,
                draft_prompt=draft_prompt
            )

        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error creating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')
            ingredient_prefill, consumable_prefill = _build_prefill_from_form(request.form)
            form_recipe = _recipe_from_form(request.form)
            return _render_recipe_form(
                recipe=form_recipe,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                is_clone=is_clone,
                cloned_from_id=cloned_from_id,
                form_values=request.form
            )

    from flask import session
    draft = session.get('tool_draft', None)
    try:
        from datetime import datetime, timezone, timedelta
        from app.utils.timezone_utils import TimezoneUtils
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
                predicted_yield_unit=(draft.get('predicted_yield_unit') or '')
            )
            cat_name = (draft.get('category_name') or '').strip()
            if cat_name:
                from app.models.product_category import ProductCategory
                cat = ProductCategory.query.filter(func.lower(ProductCategory.name) == func.lower(db.literal(cat_name))).first()
                if cat:
                    prefill.category_id = cat.id
        except Exception:
            prefill = None

    return _render_recipe_form(recipe=prefill)

@recipes_bp.route('/')
@login_required
def list_recipes():
    # Simple data retrieval - no business logic
    query = Recipe.query.filter_by(parent_recipe_id=None)
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)

    recipes = query.all()
    inventory_units = get_global_unit_list()
    return render_template('pages/recipes/recipe_list.html', recipes=recipes, inventory_units=inventory_units)

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

    except Exception as e:
        flash(f"Error loading recipe: {str(e)}", "error")
        logger.exception(f"Error viewing recipe: {str(e)}")
        return redirect(url_for('recipes.list_recipes'))


@recipes_bp.route('/<int:recipe_id>/lineage')
@login_required
def recipe_lineage(recipe_id):
    try:
        recipe = get_recipe_details(recipe_id)
    except PermissionError:
        flash("You do not have access to this recipe.", "error")
        return redirect(url_for('recipes.list_recipes'))
    except Exception as exc:
        flash(f"Unable to load recipe lineage: {exc}", "error")
        return redirect(url_for('recipes.list_recipes'))

    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    root_id = recipe.root_recipe_id or recipe.id
    relatives = (
        Recipe.query.options(joinedload(Recipe.organization))
        .filter(or_(Recipe.id == root_id, Recipe.root_recipe_id == root_id))
        .order_by(Recipe.created_at.asc())
        .all()
    )

    nodes = {rel.id: {'recipe': rel, 'children': []} for rel in relatives}
    for rel in relatives:
        parent_id = None
        edge_type = None
        if rel.parent_recipe_id and rel.parent_recipe_id in nodes:
            parent_id = rel.parent_recipe_id
            edge_type = 'variation'
        elif rel.cloned_from_id and rel.cloned_from_id in nodes:
            parent_id = rel.cloned_from_id
            edge_type = 'clone'
        elif rel.id != root_id and rel.root_recipe_id and rel.root_recipe_id in nodes:
            parent_id = rel.root_recipe_id
            edge_type = 'root'

        if parent_id and edge_type:
            nodes[parent_id]['children'].append({'id': rel.id, 'edge': edge_type})

    root_recipe = nodes.get(root_id, {'recipe': recipe})
    lineage_tree = _serialize_lineage_tree(root_recipe['recipe'], nodes, recipe.id)
    lineage_path = _build_lineage_path(recipe.id, nodes, root_id)
    events = (
        RecipeLineage.query.filter_by(recipe_id=recipe.id)
        .order_by(RecipeLineage.created_at.asc())
        .all()
    )

    origin_source_org = None
    if recipe.org_origin_purchased and recipe.origin_source_org:
        origin_source_org = recipe.origin_source_org

    org_marketplace_enabled = is_feature_enabled('FEATURE_ORG_MARKETPLACE_DASHBOARD')

    return render_template(
        'pages/recipes/recipe_lineage.html',
        recipe=recipe,
        origin_source_org=origin_source_org,
        lineage_tree=lineage_tree,
        lineage_path=lineage_path,
        lineage_events=events,
        org_marketplace_enabled=org_marketplace_enabled,
    )









@recipes_bp.route('/<int:recipe_id>/variation', methods=['GET', 'POST'])
@login_required
def create_variation(recipe_id):
    try:
        parent = get_recipe_details(recipe_id)
        if not parent:
            flash('Parent recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        if request.method == 'POST':
            target_status = _get_submission_status(request.form)
            submission = _build_recipe_submission(request.form, request.files, defaults=parent)
            if not submission.ok:
                flash(submission.error, 'error')
                ingredient_prefill, consumable_prefill = _build_prefill_from_form(request.form)
                variation_draft = _recipe_from_form(request.form, base_recipe=parent)
                variation_draft.parent_recipe_id = parent.id
                return _render_recipe_form(
                    recipe=variation_draft,
                    is_variation=True,
                    parent_recipe=parent,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=request.form
                )

            payload = dict(submission.kwargs)
            payload.update({
                'parent_recipe_id': parent.id,
                'status': target_status,
            })
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

            error_message, missing_fields = _parse_service_error(result)
            draft_prompt = _build_draft_prompt(missing_fields, target_status, error_message)
            flash(f'Error creating variation: {error_message}', 'error')
            ingredient_prefill, consumable_prefill = _build_prefill_from_form(request.form)
            variation_draft = _recipe_from_form(request.form, base_recipe=parent)
            variation_draft.parent_recipe_id = parent.id
            return _render_recipe_form(
                recipe=variation_draft,
                is_variation=True,
                parent_recipe=parent,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                form_values=request.form,
                draft_prompt=draft_prompt
            )

        new_variation = _create_variation_template(parent)
        ingredient_prefill = _serialize_assoc_rows(parent.recipe_ingredients)
        consumable_prefill = _serialize_assoc_rows(parent.recipe_consumables)

        return _render_recipe_form(
            recipe=new_variation,
            is_variation=True,
            parent_recipe=parent,
            ingredient_prefill=ingredient_prefill,
            consumable_prefill=consumable_prefill
        )

    except Exception as e:
        flash(f"Error creating variation: {str(e)}", "error")
        logger.exception(f"Error creating variation: {str(e)}")
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
        target_status = _get_submission_status(request.form)
        try:
            submission = _build_recipe_submission(request.form, request.files, defaults=recipe, existing=recipe)
            if not submission.ok:
                flash(submission.error, 'error')
                form_override = request.form
                ingredient_prefill, consumable_prefill = _build_prefill_from_form(request.form)
                return _render_recipe_form(
                    recipe=recipe,
                    edit_mode=True,
                    ingredient_prefill=ingredient_prefill,
                    consumable_prefill=consumable_prefill,
                    form_values=form_override
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
                error_message, missing_fields = _parse_service_error(result)
                draft_prompt = _build_draft_prompt(missing_fields, target_status, error_message)
                form_override = request.form
                flash(f'Error updating recipe: {error_message}', 'error')

        except Exception as e:
            logger.exception(f"Error updating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')

    # GET - show edit form
    form_data = _get_recipe_form_data()
    from ...models import Batch
    existing_batches = Batch.query.filter_by(recipe_id=recipe.id).count()

    return render_template('pages/recipes/recipe_form.html',
                         recipe=recipe,
                         edit_mode=True,
                         existing_batches=existing_batches,
                         draft_prompt=draft_prompt,
                         form_values=form_override,
                         **form_data)

@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    try:
        success, payload = duplicate_recipe(recipe_id)

        if success:
            template_recipe = payload['template']
            ingredient_prefill = _serialize_prefill_rows(payload['ingredients'])
            consumable_prefill = _serialize_prefill_rows(payload['consumables'])

            return _render_recipe_form(
                recipe=template_recipe,
                is_clone=True,
                ingredient_prefill=ingredient_prefill,
                consumable_prefill=consumable_prefill,
                cloned_from_id=payload.get('cloned_from_id'),
                form_values=None
            )
        else:
            flash(f"Error cloning recipe: {payload}", "error")

    except Exception as e:
        db.session.rollback()
        flash(f"Error cloning recipe: {str(e)}", "error")
        logger.exception(f"Error cloning recipe: {str(e)}")

    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/import', methods=['GET'])
@login_required
def import_recipe(recipe_id: int):
    """Launch the recipe import flow for public marketplace listings."""
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
    ingredient_prefill = _serialize_prefill_rows(payload['ingredients'])
    consumable_prefill = _serialize_prefill_rows(payload['consumables'])

    if recipe.is_for_sale:
        flash("Confirm your purchase before importing paid recipes.", "warning")
    else:
        flash("Review the imported recipe and click Save to add it to your workspace.", "info")

    return _render_recipe_form(
        recipe=template_recipe,
        is_clone=True,
        ingredient_prefill=ingredient_prefill,
        consumable_prefill=consumable_prefill,
        cloned_from_id=payload.get('cloned_from_id'),
        form_values=None,
        is_import=True,
    )

@recipes_bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
def delete_recipe_route(recipe_id):
    try:
        success, message = delete_recipe(recipe_id)
        if success:
            flash(message)
        else:
            flash(f'Error deleting recipe: {message}', 'error')
    except Exception as e:
        logger.error(f"Error deleting recipe {recipe_id}: {str(e)}")
        flash('An error occurred while deleting the recipe.', 'error')

    return redirect(url_for('recipes.list_recipes'))

@recipes_bp.route('/<int:recipe_id>/make-parent', methods=['POST'])
@login_required
def make_parent_recipe(recipe_id):
    """Convert a variation recipe into a standalone parent recipe"""
    try:
        recipe = db.session.get(Recipe, recipe_id)
        if not recipe:
            flash('Recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        if not recipe.parent_recipe_id:
            flash('Recipe is already a parent recipe.', 'error')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

        # Store original parent for flash message
        original_parent = recipe.parent

        # Convert variation to parent by removing parent relationship
        recipe.parent_recipe_id = None

        # Update the name to remove "Variation" suffix if present
        if recipe.name.endswith(" Variation"):
            recipe.name = recipe.name.replace(" Variation", "")

        lineage_entry = RecipeLineage(
            recipe_id=recipe.id,
            source_recipe_id=original_parent.id if original_parent else None,
            event_type='PROMOTE_TO_PARENT',
            organization_id=recipe.organization_id,
            user_id=getattr(current_user, 'id', None)
        )
        db.session.add(lineage_entry)

        db.session.commit()

        flash(f'Recipe "{recipe.name}" has been converted to a parent recipe and is no longer a variation of "{original_parent.name}".', 'success')
        logger.info(f"Converted recipe {recipe_id} from variation to parent recipe")

        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error converting recipe {recipe_id} to parent: {str(e)}")
        flash('An error occurred while converting the recipe to a parent.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

@recipes_bp.route('/<int:recipe_id>/lock', methods=['POST'])
@login_required
def lock_recipe(recipe_id):
    # Simple database operation - no business logic
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.is_locked = True
    db.session.commit()
    flash('Recipe locked successfully.')
    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

@recipes_bp.route('/<int:recipe_id>/unlock', methods=['POST'])
@login_required
def unlock_recipe(recipe_id):
    # Simple validation and database operation
    recipe = Recipe.query.get_or_404(recipe_id)
    unlock_password = request.form.get('unlock_password')

    if current_user.check_password(unlock_password):
        recipe.is_locked = False
        db.session.commit()
        flash('Recipe unlocked successfully.')
    else:
        flash('Incorrect password.', 'error')

    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

@recipes_bp.route('/units/quick-add', methods=['POST'])
@login_required
def quick_add_unit():
    """Create an org-scoped custom unit (e.g., portion count name)."""
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        unit_type = (data.get('type') or data.get('unit_type') or 'count').strip()

        if not name:
            return jsonify({'error': 'Unit name is required'}), 400

        # Enforce count type for portion names
        if unit_type != 'count':
            unit_type = 'count'

        # Check existing within org or standard
        existing = Unit.query.filter(
            func.lower(Unit.name) == func.lower(db.literal(name)),
            ((Unit.is_custom == False) | (Unit.organization_id == current_user.organization_id))
        ).first()
        if existing:
            return jsonify({
                'id': existing.id,
                'name': existing.name,
                'unit_type': existing.unit_type,
                'symbol': existing.symbol,
                'is_custom': existing.is_custom
            })

        unit = Unit(
            name=name,
            unit_type=unit_type,
            base_unit='count',
            conversion_factor=1.0,
            is_active=True,
            is_custom=True,
            is_mapped=False,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        db.session.add(unit)
        db.session.commit()
        return jsonify({
            'id': unit.id,
            'name': unit.name,
            'unit_type': unit.unit_type,
            'symbol': unit.symbol,
            'is_custom': True
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@recipes_bp.route('/ingredients/quick-add', methods=['POST'])
@login_required
def quick_add_ingredient():
    """Quick add ingredient for recipes"""
    try:
        data = request.get_json()
        name = data.get('name')
        unit = data.get('unit', 'each')
        ingredient_type = data.get('type', 'ingredient')

        if not name:
            return jsonify({'error': 'Ingredient name is required'}), 400

        # Check if ingredient already exists
        existing = InventoryItem.query.filter_by(
            name=name,
            organization_id=current_user.organization_id
        ).first()

        if existing:
            return jsonify({
                'id': existing.id,
                'name': existing.name,
                'unit': existing.unit,
                'type': existing.type,
                'exists': True
            })

        # Create new ingredient
        ingredient = InventoryItem(
            name=name,
            unit=unit,
            type=ingredient_type,
            quantity=0.0,  # Start with zero quantity
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )

        db.session.add(ingredient)
        db.session.commit()

        logger.info(f"Quick-added ingredient: {name} (ID: {ingredient.id})")

        return jsonify({
            'id': ingredient.id,
            'name': ingredient.name,
            'unit': ingredient.unit,
            'type': ingredient.type,
            'exists': False
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error quick-adding ingredient: {e}")
        return jsonify({'error': str(e)}), 500


@dataclass
class RecipeFormSubmission:
    kwargs: Dict[str, Any]
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _build_recipe_submission(form, files, *, defaults: Optional[Recipe] = None, existing: Optional[Recipe] = None) -> RecipeFormSubmission:
    ingredients = _extract_ingredients_from_form(form)
    consumables = _extract_consumables_from_form(form)
    allowed_containers = _collect_allowed_containers(form)

    portion_payload, portion_fields = _parse_portioning_from_form(form)
    category_id = _safe_int(form.get('category_id'))

    fallback_yield = getattr(defaults, 'predicted_yield', None)
    if fallback_yield is None:
        fallback_yield = 0.0
    yield_amount = _coerce_float(form.get('predicted_yield'), fallback=fallback_yield)
    fallback_unit = getattr(defaults, 'predicted_yield_unit', '') if defaults else ''
    yield_unit = form.get('predicted_yield_unit') or fallback_unit or ""

    marketplace_ok, marketplace_result = RecipeMarketplaceService.extract_submission(form, files, existing=existing)
    if not marketplace_ok:
        return RecipeFormSubmission({}, marketplace_result)

    kwargs: Dict[str, Any] = {
        'name': form.get('name'),
        'description': form.get('instructions'),
        'instructions': form.get('instructions'),
        'yield_amount': yield_amount,
        'yield_unit': yield_unit,
        'ingredients': ingredients,
        'consumables': consumables,
        'allowed_containers': allowed_containers,
        'label_prefix': form.get('label_prefix'),
        'category_id': category_id,
        'portioning_data': portion_payload,
        'is_portioned': portion_fields['is_portioned'],
        'portion_name': portion_fields['portion_name'],
        'portion_count': portion_fields['portion_count'],
        'portion_unit_id': portion_fields['portion_unit_id'],
    }
    kwargs.update(marketplace_result['marketplace'])
    kwargs.update(marketplace_result['cover'])

    return RecipeFormSubmission(kwargs)


def _collect_allowed_containers(form) -> list[int]:
    containers: list[int] = []
    for raw in form.getlist('allowed_containers[]'):
        value = _safe_int(raw)
        if value:
            containers.append(value)
    return containers


def _parse_portioning_from_form(form) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    truthy = {'true', '1', 'yes', 'on'}
    flag = str(form.get('is_portioned') or '').strip().lower() in truthy
    default_fields = {
        'is_portioned': False,
        'portion_name': None,
        'portion_count': None,
        'portion_unit_id': None,
    }
    if not flag:
        return None, default_fields

    portion_name = (form.get('portion_name') or '').strip() or None
    portion_count = _safe_int(form.get('portion_count'))
    portion_unit_id = _ensure_portion_unit(portion_name)

    payload = {
        'is_portioned': True,
        'portion_name': portion_name,
        'portion_count': portion_count,
        'portion_unit_id': portion_unit_id,
    }
    return payload, payload.copy()


def _ensure_portion_unit(portion_name: Optional[str]) -> Optional[int]:
    if not portion_name:
        return None

    try:
        existing = Unit.query.filter(Unit.name == portion_name).order_by(
            (Unit.organization_id == current_user.organization_id).desc()
        ).first()
    except Exception:
        existing = None

    if existing:
        return existing.id

    if not getattr(current_user, 'is_authenticated', False):
        return None

    try:
        unit = Unit(
            name=portion_name,
            unit_type='count',
            base_unit='count',
            conversion_factor=1.0,
            is_active=True,
            is_custom=True,
            is_mapped=False,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        db.session.add(unit)
        db.session.flush()
        return unit.id
    except Exception:
        db.session.rollback()
        return None


def _coerce_float(value: Any, *, fallback: float = 0.0) -> float:
    if value in (None, ''):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback

# Helper functions to keep controllers clean
def _render_recipe_form(recipe=None, **context):
    form_data = _get_recipe_form_data()
    payload = {**form_data, **context}
    return render_template('pages/recipes/recipe_form.html', recipe=recipe, **payload)


def _recipe_from_form(form, base_recipe=None):
    recipe = Recipe()
    recipe.name = form.get('name') or (base_recipe.name if base_recipe else '')
    recipe.instructions = form.get('instructions') or (base_recipe.instructions if base_recipe else '')
    recipe.label_prefix = form.get('label_prefix') or (base_recipe.label_prefix if base_recipe else '')
    recipe.category_id = _safe_int(form.get('category_id')) or (base_recipe.category_id if base_recipe else None)
    recipe.parent_recipe_id = base_recipe.parent_recipe_id if base_recipe and getattr(base_recipe, 'parent_recipe_id', None) else None

    # Product store URL
    product_store_url = form.get('product_store_url')
    if product_store_url is not None:
        recipe.product_store_url = product_store_url.strip() or None

    # Product group ID
    recipe.product_group_id = _safe_int(form.get('product_group_id')) or (base_recipe.product_group_id if base_recipe else None)

    try:
        recipe.predicted_yield = float(form.get('predicted_yield')) if form.get('predicted_yield') not in (None, '') else (base_recipe.predicted_yield if base_recipe else None)
    except (TypeError, ValueError):
        recipe.predicted_yield = base_recipe.predicted_yield if base_recipe else None
    recipe.predicted_yield_unit = form.get('predicted_yield_unit') or (base_recipe.predicted_yield_unit if base_recipe else '')

    recipe.allowed_containers = [int(id) for id in form.getlist('allowed_containers[]') if id] or (list(base_recipe.allowed_containers) if base_recipe and base_recipe.allowed_containers else [])

    is_portioned = form.get('is_portioned') == 'true'
    recipe.is_portioned = is_portioned or (base_recipe.is_portioned if base_recipe else False)
    recipe.portion_name = form.get('portion_name') or (base_recipe.portion_name if base_recipe else None)
    try:
        recipe.portion_count = int(form.get('portion_count')) if form.get('portion_count') else (base_recipe.portion_count if base_recipe else None)
    except (TypeError, ValueError):
        recipe.portion_count = base_recipe.portion_count if base_recipe else None
    recipe.portioning_data = {
        'is_portioned': recipe.is_portioned,
        'portion_name': recipe.portion_name,
        'portion_count': recipe.portion_count
    } if recipe.is_portioned else None

    return recipe


def _build_prefill_from_form(form):
    ingredient_ids = [ _safe_int(val) for val in form.getlist('ingredient_ids[]') ]
    amounts = form.getlist('amounts[]')
    units = form.getlist('units[]')
    global_ids = [ _safe_int(val) for val in form.getlist('global_item_ids[]') ]

    consumable_ids = [ _safe_int(val) for val in form.getlist('consumable_ids[]') ]
    consumable_amounts = form.getlist('consumable_amounts[]')
    consumable_units = form.getlist('consumable_units[]')

    lookup_ids = [i for i in ingredient_ids + consumable_ids if i]
    name_lookup = _lookup_inventory_names(lookup_ids)

    ingredient_rows = []
    for ing_id, gi_id, amt, unit in zip_longest(ingredient_ids, global_ids, amounts, units, fillvalue=None):
        if not any([ing_id, gi_id, amt, unit]):
            continue
        ingredient_rows.append({
            'inventory_item_id': ing_id,
            'global_item_id': gi_id,
            'quantity': amt,
            'unit': unit,
            'name': name_lookup.get(ing_id, '')
        })

    consumable_rows = []
    for cid, amt, unit in zip_longest(consumable_ids, consumable_amounts, consumable_units, fillvalue=None):
        if not any([cid, amt, unit]):
            continue
        consumable_rows.append({
            'inventory_item_id': cid,
            'quantity': amt,
            'unit': unit,
            'name': name_lookup.get(cid, '')
        })

    return ingredient_rows, consumable_rows


def _serialize_prefill_rows(rows):
    ids = [row.get('item_id') for row in rows if row.get('item_id')]
    name_lookup = _lookup_inventory_names(ids)
    serialized = []
    for row in rows:
        item_id = row.get('item_id')
        serialized.append({
            'inventory_item_id': item_id,
            'global_item_id': row.get('global_item_id'),
            'quantity': row.get('quantity'),
            'unit': row.get('unit'),
            'name': row.get('name') or name_lookup.get(item_id, '')
        })
    return serialized


def _serialize_assoc_rows(associations):
    serialized = []
    for assoc in associations:
        serialized.append({
            'inventory_item_id': assoc.inventory_item_id,
            'quantity': assoc.quantity,
            'unit': assoc.unit,
            'name': assoc.inventory_item.name if assoc.inventory_item else ''
        })
    return serialized


def _serialize_lineage_tree(node_recipe: Recipe, nodes: dict, current_id: int) -> dict:
    node_payload = {
        'id': node_recipe.id,
        'name': node_recipe.name,
        'organization_name': node_recipe.organization.name if node_recipe.organization else None,
        'organization_id': node_recipe.organization_id,
        'origin_type': node_recipe.org_origin_type,
        'origin_purchased': node_recipe.org_origin_purchased,
        'is_current': node_recipe.id == current_id,
        'status': node_recipe.status,
        'children': [],
    }

    for child in nodes.get(node_recipe.id, {}).get('children', []):
        child_recipe = nodes[child['id']]['recipe']
        node_payload['children'].append({
            'edge_type': child['edge'],
            'node': _serialize_lineage_tree(child_recipe, nodes, current_id)
        })

    return node_payload


def _build_lineage_path(target_id: int, nodes: dict, root_id: int | None) -> list[int]:
    path: list[int] = []
    seen: set[int] = set()
    current_id = target_id

    while current_id and current_id not in seen:
        path.append(current_id)
        seen.add(current_id)
        recipe = nodes.get(current_id, {}).get('recipe')
        if not recipe:
            break
        if recipe.parent_recipe_id and recipe.parent_recipe_id in nodes:
            current_id = recipe.parent_recipe_id
        elif recipe.cloned_from_id and recipe.cloned_from_id in nodes:
            current_id = recipe.cloned_from_id
        elif (
            recipe.root_recipe_id
            and recipe.root_recipe_id in nodes
            and recipe.id != recipe.root_recipe_id
        ):
            current_id = recipe.root_recipe_id
        else:
            current_id = None

    if root_id and root_id not in path:
        path.append(root_id)

    return list(reversed(path))


def _lookup_inventory_names(item_ids):
    if not item_ids:
        return {}
    unique_ids = list({item_id for item_id in item_ids if item_id})
    if not unique_ids:
        return {}
    items = InventoryItem.query.filter(InventoryItem.id.in_(unique_ids)).all()
    return {item.id: item.name for item in items}


def _safe_int(value):
    try:
        return int(value) if value not in (None, '', []) else None
    except (TypeError, ValueError):
        return None


def _extract_ingredients_from_form(form):
    """Extract ingredient data from form submission.
    Supports inventory items and selected global items (auto-creates zero-qty inventory when needed).
    """
    ingredients = []
    ingredient_ids = form.getlist('ingredient_ids[]')
    global_item_ids = form.getlist('global_item_ids[]')
    amounts = form.getlist('amounts[]')
    units = form.getlist('units[]')

    # Normalize lengths
    max_len = max(len(ingredient_ids), len(global_item_ids), len(amounts), len(units))
    ingredient_ids += [''] * (max_len - len(ingredient_ids))
    global_item_ids += [''] * (max_len - len(global_item_ids))
    amounts += [''] * (max_len - len(amounts))
    units += [''] * (max_len - len(units))

    for ing_id, gi_id, amt, unit in zip(ingredient_ids, global_item_ids, amounts, units):
        if not amt or not unit:
            continue

        try:
            quantity = float(str(amt).strip())
        except (ValueError, TypeError):
            logger.error(f"Invalid quantity provided for ingredient line: {amt}")
            continue

        item_id = None
        if ing_id:
            try:
                item_id = int(ing_id)
            except (ValueError, TypeError):
                item_id = None

        # If no inventory item selected but a global item is selected, try to map to an existing inventory item
        if not item_id and gi_id:
            try:
                gi = db.session.get(GlobalItem, int(gi_id)) if gi_id else None
            except Exception:
                gi = None

            if gi:
                # 1) Prefer existing inventory item already linked to this global item
                try:
                    existing = InventoryItem.query.filter_by(
                        organization_id=current_user.organization_id,
                        global_item_id=gi.id,
                        type=gi.item_type
                    ).order_by(InventoryItem.id.asc()).first()
                except Exception:
                    existing = None

                if existing:
                    item_id = int(existing.id)
                else:
                    # 2) Fall back to name match within org and same type
                    try:
                        name_match = (
                            InventoryItem.query
                            .filter(
                                InventoryItem.organization_id == current_user.organization_id,
                                func.lower(InventoryItem.name) == func.lower(db.literal(gi.name)),
                                InventoryItem.type == gi.item_type
                            )
                            .order_by(InventoryItem.id.asc())
                            .first()
                        )
                    except Exception:
                        name_match = None

                    if name_match:
                        # Optionally link it for future dedupe
                        try:
                            name_match.global_item_id = gi.id
                            name_match.ownership = 'global'
                            db.session.flush()
                        except Exception:
                            db.session.rollback()
                        item_id = int(name_match.id)
                    else:
                        # 3) Create a new zero-qty inventory item linked to global
                        form_like = {
                            'name': gi.name,
                            'type': gi.item_type,
                            'unit': gi.default_unit or '',
                            'global_item_id': gi.id
                        }

                        success, message, created_id = create_inventory_item(
                            form_data=form_like,
                            organization_id=current_user.organization_id,
                            created_by=current_user.id
                        )
                        if not success:
                            logger.error(f"Failed to auto-create inventory for global item {gi.id}: {message}")
                        else:
                            item_id = int(created_id)
            else:
                logger.error(f"Global item not found for id {gi_id}")

        if item_id:
            ingredients.append({
                'item_id': item_id,
                'quantity': quantity,
                'unit': (unit or '').strip()
            })

    return ingredients

def _extract_consumables_from_form(form):
    """Extract consumable data from form submission"""
    consumables = []
    ids = form.getlist('consumable_ids[]')
    amounts = form.getlist('consumable_amounts[]')
    units = form.getlist('consumable_units[]')
    for item_id, amt, unit in zip(ids, amounts, units):
        if item_id and amt and unit:
            try:
                consumables.append({
                    'item_id': int(item_id),
                    'quantity': float(amt.strip()),
                    'unit': unit.strip()
                })
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid consumable data: {e}")
                continue
    return consumables


def _get_submission_status(form):
    mode = (form.get('save_mode') or '').strip().lower()
    return 'draft' if mode == 'draft' else 'published'


def _parse_service_error(error):
    if isinstance(error, dict):
        message = error.get('error') or error.get('message') or 'An error occurred'
        missing_fields = error.get('missing_fields') or []
        return message, missing_fields
    return str(error), []


def _build_draft_prompt(missing_fields, attempted_status, message):
    if missing_fields and attempted_status != 'draft':
        return {
            'missing_fields': missing_fields,
            'message': message
        }
    return None


def _get_recipe_form_data():
    """Get common data needed for recipe forms"""
    ingredients_query = InventoryItem.query.filter(
        ~InventoryItem.type.in_(['product', 'product-reserved'])
    ).order_by(InventoryItem.name)

    if current_user.organization_id:
        ingredients_query = ingredients_query.filter_by(organization_id=current_user.organization_id)

    all_ingredients = ingredients_query.all()
    units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
    inventory_units = get_global_unit_list()

    # Categories for dropdown
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    product_groups = RecipeProductGroup.query.filter_by(is_active=True).order_by(
        RecipeProductGroup.display_order.asc(), RecipeProductGroup.name.asc()
    ).all()

    return {
        'all_ingredients': all_ingredients,
        'units': units,
        'inventory_units': inventory_units,
        'product_categories': categories,
        'product_groups': product_groups,
        'recipe_sharing_enabled': _is_recipe_sharing_enabled()
    }


def _is_recipe_sharing_enabled():
    try:
        enabled = is_feature_enabled('FEATURE_RECIPE_SHARING_CONTROLS')
    except Exception:
        enabled = False
    if current_user.is_authenticated and getattr(current_user, 'user_type', '') == 'developer':
        return True
    return enabled

def _format_stock_results(ingredients):
    """Format ingredient availability for frontend"""
    return [
        {
            'ingredient_id': ingredient['ingredient_id'],
            'ingredient_name': ingredient['ingredient_name'],
            'needed_amount': ingredient['required_quantity'],
            'unit': ingredient['required_unit'],
            'available': ingredient['is_available'],
            'available_quantity': ingredient['available_quantity'],
            'shortage': ingredient['shortage']
        }
        for ingredient in ingredients
    ]

def _create_variation_template(parent):
    """Create a template variation object for the form"""
    # Generate variation prefix suggestion
    variation_prefix = ""
    if parent.label_prefix:
        # Count existing variations to suggest next number
        existing_variations = Recipe.query.filter_by(parent_recipe_id=parent.id).count()
        variation_prefix = f"{parent.label_prefix}V{existing_variations + 1}"

    template = Recipe(
        name=f"{parent.name} Variation",
        instructions=parent.instructions,
        label_prefix=variation_prefix,
        parent_recipe_id=parent.id,
        predicted_yield=parent.predicted_yield,
        predicted_yield_unit=parent.predicted_yield_unit,
        category_id=parent.category_id
    )

    # Carry over structured settings so the entire form mirrors the parent
    template.allowed_containers = list(parent.allowed_containers or [])

    if parent.portioning_data:
        template.portioning_data = parent.portioning_data.copy() if isinstance(parent.portioning_data, dict) else parent.portioning_data
    template.is_portioned = parent.is_portioned
    template.portion_name = parent.portion_name
    template.portion_count = parent.portion_count
    template.portion_unit_id = parent.portion_unit_id

    if parent.category_data:
        template.category_data = parent.category_data.copy() if isinstance(parent.category_data, dict) else parent.category_data
    template.product_group_id = parent.product_group_id
    template.skin_opt_in = parent.skin_opt_in
    template.sharing_scope = 'private'
    template.is_public = False
    template.is_for_sale = False

    # Marketplace fields
    template.product_store_url = parent.product_store_url
    # Removed recipe_collection_group_id as per user request

    return template