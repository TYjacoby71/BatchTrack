from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import recipes_bp
from app.extensions import db
from app.models import Recipe, InventoryItem, GlobalItem
from app.utils.permissions import require_permission

from app.services.recipe_service import (
    create_recipe, update_recipe, delete_recipe, get_recipe_details,
    duplicate_recipe
)

from app.utils.unit_utils import get_global_unit_list
from app.services.inventory_adjustment import create_inventory_item
from app.models.unit import Unit
from app.models.product_category import ProductCategory
import logging
from sqlalchemy import func

logger = logging.getLogger(__name__)

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        try:
            # Extract form data and delegate to service
            ingredients = _extract_ingredients_from_form(request.form)

            # Portioning inputs from form (optional) - absolute minimal fields
            portioning_payload = None
            try:
                is_portioned = request.form.get('is_portioned', '') == 'true'
                if is_portioned:
                    portion_name = (request.form.get('portion_name') or '').strip() or None
                    # Ensure portion_name is a valid Unit (count type). Use name as the key.
                    unit_id = None
                    if portion_name:
                        try:
                            existing = Unit.query.filter(Unit.name == portion_name).order_by((Unit.organization_id == current_user.organization_id).desc()).first()
                        except Exception:
                            existing = None
                        if not existing:
                            try:
                                u = Unit(
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
                                db.session.add(u)
                                db.session.flush()
                                unit_id = u.id
                            except Exception:
                                db.session.rollback()
                        else:
                            unit_id = existing.id
                    portioning_payload = {
                        'is_portioned': True,
                        'portion_count': int(request.form.get('portion_count') or 0),
                        'portion_name': portion_name,
                        'portion_unit_id': unit_id
                    }
            except Exception:
                portioning_payload = None

            success, result = create_recipe(
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or "",
                ingredients=ingredients,
                consumables=_extract_consumables_from_form(request.form),
                allowed_containers=[int(id) for id in request.form.getlist('allowed_containers[]') if id] or [],
                label_prefix=request.form.get('label_prefix'),
                category_id=int(request.form.get('category_id')) if request.form.get('category_id') else None,
                portioning_data=portioning_payload,
                # Absolute columns mirror JSON for clarity
                is_portioned=(portioning_payload.get('is_portioned') if portioning_payload else False),
                portion_name=(portioning_payload.get('portion_name') if portioning_payload else None),
                portion_count=(portioning_payload.get('portion_count') if portioning_payload else None)
            )

            if success:
                # Detect inline-created custom items (no global_item_id and zero quantity)
                try:
                    created_names = []
                    for ing in ingredients:
                        from app.models import InventoryItem as _Inv
                        item = _Inv.query.get(ing['item_id'])
                        if item and not getattr(item, 'global_item_id', None) and float(getattr(item, 'quantity', 0) or 0) == 0.0:
                            created_names.append(item.name)
                    if created_names:
                        flash(f"Added {len(created_names)} new inventory item(s) from this recipe: " + ", ".join(created_names))
                except Exception:
                    pass
                flash('Recipe created successfully with ingredients.')
                # Clear tool draft after successful save
                try:
                    from flask import session as _session
                    _session.pop('tool_draft', None)
                    _session.pop('tool_draft_meta', None)
                except Exception:
                    pass
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
            else:
                flash(f'Error creating recipe: {result}', 'error')

        except Exception as e:
            logger.exception(f"Error creating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')

    # GET request - show form
    # Prefill from public tools draft (if present)
    from flask import session
    draft = session.get('tool_draft', None)
    # Expire stale drafts (>72 hours) so they don't linger indefinitely
    try:
        from datetime import datetime, timedelta
        meta = session.get('tool_draft_meta') or {}
        created_at = meta.get('created_at')
        if created_at:
            created_dt = datetime.fromisoformat(created_at)
            if datetime.utcnow() - created_dt > timedelta(hours=72):
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
            # Attempt to pre-select category by name if provided
            cat_name = (draft.get('category_name') or '').strip()
            if cat_name:
                from app.models.product_category import ProductCategory
                cat = ProductCategory.query.filter(func.lower(ProductCategory.name) == func.lower(db.literal(cat_name))).first()
                if cat:
                    prefill.category_id = cat.id
        except Exception:
            prefill = None

    form_data = _get_recipe_form_data()
    return render_template('pages/recipes/recipe_form.html', recipe=prefill, **form_data)

@recipes_bp.route('/')
@login_required
def list_recipes():
    # Simple data retrieval - no business logic
    query = Recipe.query.filter_by(parent_id=None)
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
        return render_template('pages/recipes/view_recipe.html', recipe=recipe, inventory_units=inventory_units)

    except Exception as e:
        flash(f"Error loading recipe: {str(e)}", "error")
        logger.exception(f"Error viewing recipe: {str(e)}")
        return redirect(url_for('recipes.list_recipes'))









@recipes_bp.route('/<int:recipe_id>/variation', methods=['GET', 'POST'])
@login_required
def create_variation(recipe_id):
    try:
        parent = get_recipe_details(recipe_id)
        if not parent:
            flash('Parent recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        if request.method == 'POST':
            # Extract ingredients and delegate to service
            ingredients = _extract_ingredients_from_form(request.form)

            # Get label prefix or generate from parent
            label_prefix = request.form.get('label_prefix')
            if not label_prefix and parent.label_prefix:
                # Auto-generate variation prefix from parent
                label_prefix = ""  # Let the service handle variation prefix generation

            success, result = create_recipe(
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or parent.predicted_yield or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or parent.predicted_yield_unit or "",
                ingredients=ingredients,
                consumables=_extract_consumables_from_form(request.form),
                parent_id=parent.id,
                allowed_containers=[int(id) for id in request.form.getlist('allowed_containers[]') if id] or [],
                label_prefix=label_prefix
            )

            if success:
                flash('Recipe variation created successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
            else:
                flash(f'Error creating variation: {result}', 'error')

        # GET - show variation form with parent data
        form_data = _get_recipe_form_data()
        new_variation = _create_variation_template(parent)

        # Extract parent ingredients for prefill
        ingredients = [(ri.inventory_item_id, ri.quantity, ri.unit) for ri in parent.recipe_ingredients]
        consumables = [(rc.inventory_item_id, rc.quantity, rc.unit) for rc in parent.recipe_consumables]

        return render_template('pages/recipes/recipe_form.html',
                             recipe=new_variation,
                             is_variation=True,
                             parent_recipe=parent,
                             ingredient_prefill=ingredients,
                             consumable_prefill=consumables,
                             **form_data)

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

    if request.method == 'POST':
        try:
            ingredients = _extract_ingredients_from_form(request.form)

            portioning_payload = None
            try:
                is_portioned = request.form.get('is_portioned', '') == 'true'
                if is_portioned:
                    portion_name = (request.form.get('portion_name') or '').strip() or None
                    unit_id = None
                    if portion_name:
                        try:
                            existing = Unit.query.filter(Unit.name == portion_name).order_by((Unit.organization_id == current_user.organization_id).desc()).first()
                        except Exception:
                            existing = None
                        if not existing:
                            try:
                                u = Unit(
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
                                db.session.add(u)
                                db.session.flush()
                                unit_id = u.id
                            except Exception:
                                db.session.rollback()
                        else:
                            unit_id = existing.id
                    portioning_payload = {
                        'is_portioned': True,
                        'portion_count': int(request.form.get('portion_count') or 0),
                        'portion_name': portion_name,
                        'portion_unit_id': unit_id
                    }
            except Exception:
                portioning_payload = None

            # Parse yield amount safely: if blank, do not override existing yield
            _yield_param = request.form.get('predicted_yield')
            try:
                parsed_yield_amount = float(_yield_param) if _yield_param not in (None, '') else None
            except (ValueError, TypeError):
                parsed_yield_amount = None

            success, result = update_recipe(
                recipe_id=recipe_id,
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=parsed_yield_amount,
                yield_unit=request.form.get('predicted_yield_unit') or "",
                ingredients=ingredients,
                consumables=_extract_consumables_from_form(request.form),
                allowed_containers=[int(id) for id in request.form.getlist('allowed_containers[]') if id] or [],
                label_prefix=request.form.get('label_prefix'),
                category_id=int(request.form.get('category_id')) if request.form.get('category_id') else None,
                portioning_data=portioning_payload,
                is_portioned=(portioning_payload.get('is_portioned') if portioning_payload else False),
                portion_name=(portioning_payload.get('portion_name') if portioning_payload else None),
                portion_count=(portioning_payload.get('portion_count') if portioning_payload else None)
            )

            if success:
                flash('Recipe updated successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
            else:
                flash(f'Error updating recipe: {result}', 'error')

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
                         **form_data)

@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    try:
        success, result = duplicate_recipe(recipe_id)

        if success:
            # Get the recipe data but don't commit yet
            cloned_recipe = result
            
            # Extract data before rollback
            clone_data = {
                'name': cloned_recipe.name,
                'instructions': cloned_recipe.instructions,
                'label_prefix': cloned_recipe.label_prefix,
                'predicted_yield': cloned_recipe.predicted_yield,
                'predicted_yield_unit': cloned_recipe.predicted_yield_unit,
                'allowed_containers': cloned_recipe.allowed_containers
            }
            
            ingredients = [(ri.inventory_item_id, ri.quantity, ri.unit) for ri in cloned_recipe.recipe_ingredients]
            consumables = [(rc.inventory_item_id, rc.quantity, rc.unit) for rc in cloned_recipe.recipe_consumables]
            
            # Rollback the transaction - user will edit and save properly
            db.session.rollback()
            
            # Create template object with extracted data
            template_recipe = Recipe(**clone_data)
            
            form_data = _get_recipe_form_data()

            return render_template('pages/recipes/recipe_form.html',
                                recipe=template_recipe,
                                is_clone=True,
                                ingredient_prefill=ingredients,
                                consumable_prefill=consumables,
                                **form_data)
        else:
            flash(f"Error cloning recipe: {result}", "error")

    except Exception as e:
        flash(f"Error cloning recipe: {str(e)}", "error")
        logger.exception(f"Error cloning recipe: {str(e)}")

    return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

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

# Helper functions to keep controllers clean
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

    return {
        'all_ingredients': all_ingredients,
        'units': units,
        'inventory_units': inventory_units,
        'product_categories': categories
    }

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
        existing_variations = Recipe.query.filter_by(parent_id=parent.id).count()
        variation_prefix = f"{parent.label_prefix}V{existing_variations + 1}"
    
    return Recipe(
        name=f"{parent.name} Variation",
        instructions=parent.instructions,
        label_prefix=variation_prefix,
        parent_id=parent.id,
        predicted_yield=parent.predicted_yield,
        predicted_yield_unit=parent.predicted_yield_unit
    )