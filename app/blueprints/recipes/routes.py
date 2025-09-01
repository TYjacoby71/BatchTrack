from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import recipes_bp
from app.extensions import db
from app.models import Recipe, InventoryItem
from app.utils.permissions import require_permission
from app.utils.unit_utils import get_global_unit_list
from app.models.unit import Unit
from app.services.recipe_service import (
    create_recipe, update_recipe, delete_recipe, get_recipe_details,
    duplicate_recipe
)
import logging

logger = logging.getLogger(__name__)

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.create')
def create_recipe():
    if request.method == 'POST':
        try:
            # Extract form data and delegate to service
            ingredients = _extract_ingredients_from_form(request.form)

            success, result = create_recipe(
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or "",
                ingredients=ingredients,
                allowed_containers=[int(id) for id in request.form.getlist('allowed_containers[]') if id] or [],
                label_prefix=request.form.get('label_prefix')
            )

            if success:
                flash('Recipe created successfully with ingredients.')
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
            else:
                flash(f'Error creating recipe: {result}', 'error')

        except Exception as e:
            logger.exception(f"Error creating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')

    # GET request - show form
    form_data = _get_recipe_form_data()
    return render_template('pages/recipes/create_recipe.html', recipe=None, **form_data)

@recipes_bp.route('/')
@login_required
@require_permission('recipes.view')
def list_recipes():
    # Simple data retrieval - no business logic
    query = Recipe.query.filter_by(parent_id=None)
    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)

    recipes = query.all()
    inventory_units = get_global_unit_list()
    return render_template('pages/recipes/list_recipes.html', recipes=recipes, inventory_units=inventory_units)

@recipes_bp.route('/<int:recipe_id>')
@login_required
@require_permission('recipes.view')
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

            success, result = create_recipe(
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or parent.predicted_yield or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or parent.predicted_yield_unit or "",
                ingredients=ingredients,
                parent_id=parent.id,
                allowed_containers=[int(id) for id in request.form.getlist('allowed_containers[]') if id] or [],
                label_prefix=request.form.get('label_prefix')
            )

            if success:
                flash('Recipe variation created successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=result.id))
            else:
                flash(f'Error creating variation: {result}', 'error')

        # GET - show variation form with parent data
        form_data = _get_recipe_form_data()
        new_variation = _create_variation_template(parent)

        return render_template('pages/recipes/create_recipe.html',
                             recipe=new_variation,
                             is_variation=True,
                             parent_recipe=parent,
                             **form_data)

    except Exception as e:
        flash(f"Error creating variation: {str(e)}", "error")
        logger.exception(f"Error creating variation: {str(e)}")
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.edit')
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

            success, result = update_recipe(
                recipe_id=recipe_id,
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or "",
                ingredients=ingredients,
                allowed_containers=[int(id) for id in request.form.getlist('allowed_containers[]') if id] or [],
                label_prefix=request.form.get('label_prefix')
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

    return render_template('pages/recipes/edit_recipe.html',
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
            new_recipe = result
            ingredients = [(ri.inventory_item_id, ri.quantity, ri.unit) for ri in new_recipe.recipe_ingredients]
            form_data = _get_recipe_form_data()

            # Don't save to DB yet - let user edit first
            db.session.rollback()

            return render_template('pages/recipes/create_recipe.html',
                                recipe=new_recipe,
                                is_clone=True,
                                ingredient_prefill=ingredients,
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
def quick_add_unit():
    # Simple database operation
    data = request.get_json()
    name = data.get('name')
    type = data.get('type', 'volume')

    try:
        unit = Unit(name=name, type=type)
        db.session.add(unit)
        db.session.commit()
        return jsonify({'name': unit.name, 'type': unit.type})
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
    """Extract ingredient data from form submission"""
    ingredients = []
    ingredient_ids = form.getlist('ingredient_ids[]')
    amounts = form.getlist('amounts[]')
    units = form.getlist('units[]')

    for ing_id, amt, unit in zip(ingredient_ids, amounts, units):
        if ing_id and amt and unit:
            try:
                ingredients.append({
                    'item_id': int(ing_id),
                    'quantity': float(amt.strip()),
                    'unit': unit.strip()
                })
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid ingredient data: {e}")
                continue

    return ingredients

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

    return {
        'all_ingredients': all_ingredients,
        'units': units,
        'inventory_units': inventory_units
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
    return Recipe(
        name=f"{parent.name} Variation",
        instructions=parent.instructions,
        label_prefix=parent.label_prefix,
        parent_id=parent.id,
        predicted_yield=parent.predicted_yield,
        predicted_yield_unit=parent.predicted_yield_unit
    )