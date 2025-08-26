from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from . import recipes_bp
from app.extensions import db
from app.models import Recipe, InventoryItem
from app.utils.permissions import require_permission

from app.services.recipe_service import (
    create_recipe, update_recipe, delete_recipe, get_recipe_details,
    duplicate_recipe
)
from app.services.production_planning import plan_production_comprehensive
from app.services.production_planning._container_management import get_container_plan_for_api
from app.utils.unit_utils import get_global_unit_list
from app.models.unit import Unit
import logging

logger = logging.getLogger(__name__)

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
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
    return render_template('pages/recipes/recipe_form.html', recipe=None, **form_data)

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

@recipes_bp.route('/<int:recipe_id>/auto-fill-containers', methods=['POST'])
@login_required
@require_permission('recipes.plan_production')
def auto_fill_containers(recipe_id):
    """Auto-fill container selection for recipe"""
    try:
        data = request.get_json()
        scale = float(data.get('scale', 1.0))
        yield_amount = float(data.get('yield_amount'))
        yield_unit = data.get('yield_unit')

        # Get recipe with all relationships loaded
        from app.models import Recipe, RecipeIngredient
        from sqlalchemy.orm import joinedload
        recipe = Recipe.query.options(
            joinedload(Recipe.recipe_ingredients).joinedload(RecipeIngredient.inventory_item)
        ).get(recipe_id)

        if not recipe:
            return jsonify({'success': False, 'error': 'Recipe not found'}), 404

        # Delegate to production planning service
        from app.services.production_planning._container_management import analyze_container_options
        strategy, options = analyze_container_options(
            recipe=recipe,
            scale=scale,
            preferred_container_id=None,
            organization_id=current_user.organization_id
        )

        # Format result to match expected frontend format
        if strategy and options:
            result = {
                'success': True,
                'container_selection': [{
                    'id': opt.container_id,
                    'name': opt.container_name,
                    'capacity': opt.storage_capacity,
                    'unit': opt.storage_unit,
                    'quantity': opt.containers_needed,
                    'stock_qty': opt.available_quantity,
                    'available_quantity': opt.available_quantity
                } for opt in options],
                'total_capacity': sum(opt.storage_capacity * opt.containers_needed for opt in options),
                'containment_percentage': strategy.average_fill_percentage if strategy else 0
            }
        else:
            result = {'success': False, 'error': 'No suitable containers found'}

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in auto-fill containers: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@recipes_bp.route('/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
@require_permission('recipes.plan_production')
def plan_production_route(recipe_id):
    """Thin controller for production planning - delegates to service"""
    recipe = get_recipe_details(recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    if request.method == 'POST':
        try:
            # Handle both JSON and form data
            if request.is_json:
                data = request.get_json()
            else:
                data = request.form.to_dict()

            scale = float(data.get('scale', 1.0))
            container_id = data.get('container_id')

            # Delegate to service - no business logic here
            planning_result = plan_production_comprehensive(recipe_id, scale, container_id)

            if planning_result.get('success', False):
                return jsonify({
                    'success': True,
                    'stock_results': planning_result.get('stock_results', []),
                    'all_available': planning_result.get('all_available', False),
                    'scale': scale,
                    'cost_info': planning_result.get('cost_info', {}),
                    'all_ok': planning_result.get('all_available', False)  # For backwards compatibility
                })
            else:
                error_msg = planning_result.get('error') or planning_result.get('message') or 'Production planning failed'
                return jsonify({'success': False, 'error': error_msg}), 500

        except Exception as e:
            logger.error(f"Error in production planning: {str(e)}")
            return jsonify({'success': False, 'error': 'Production planning failed'}), 500

    # GET request - show planning form
    return render_template('pages/recipes/plan_production.html', recipe=recipe)

@recipes_bp.route('/<int:recipe_id>/debug/containers')
@login_required
@require_permission('recipes.plan_production')
def debug_recipe_containers(recipe_id):
    """Debug endpoint to check available containers for recipe"""
    try:
        from app.models import Recipe, InventoryItem, IngredientCategory

        recipe = Recipe.query.get(recipe_id)
        if not recipe:
            return jsonify({'error': 'Recipe not found'}), 404

        # Check for allowed containers
        allowed = []
        if hasattr(recipe, 'allowed_containers'):
            allowed = [str(c) for c in recipe.allowed_containers] if recipe.allowed_containers else []

        # Get all available containers in org
        container_category = IngredientCategory.query.filter_by(
            name='Container',
            organization_id=current_user.organization_id
        ).first()

        all_containers = []
        if container_category:
            containers = InventoryItem.query.filter_by(
                organization_id=current_user.organization_id,
                category_id=container_category.id
            ).all()
            all_containers = [{'id': c.id, 'name': c.name, 'capacity': getattr(c, 'capacity', 0)} for c in containers]

        return jsonify({
            'recipe_id': recipe_id,
            'recipe_name': recipe.name,
            'allowed_containers': allowed,
            'all_containers': all_containers,
            'container_category_found': container_category is not None
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@recipes_bp.route('/<int:recipe_id>/plan/container', methods=['POST'])
@login_required
@require_permission('recipes.plan_production')
def plan_container_route(recipe_id):
    """API route to get container plan for a recipe"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        scale = float(data.get('scale', 1.0))
        yield_amount = float(data.get('yield_amount'))
        yield_unit = data.get('yield_unit')
        preferred_container_id = data.get('preferred_container_id')

        if not scale or not yield_amount or not yield_unit:
            return jsonify({"error": "Scale, yield amount, and yield unit are required"}), 400

        # Delegate to service
        container_plan = get_container_plan_for_api(
            recipe_id=recipe_id,
            scale=scale,
            yield_amount=yield_amount,
            yield_unit=yield_unit,
            preferred_container_id=preferred_container_id,
            organization_id=current_user.organization_id
        )

        return jsonify(container_plan)

    except Exception as e:
        logger.error(f"Error in container planning API: {e}")
        return jsonify({"error": str(e)}), 500

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

        return render_template('pages/recipes/recipe_form.html',
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
            new_recipe = result
            ingredients = [(ri.inventory_item_id, ri.quantity, ri.unit) for ri in new_recipe.recipe_ingredients]
            form_data = _get_recipe_form_data()

            # Don't save to DB yet - let user edit first
            db.session.rollback()

            return render_template('pages/recipes/recipe_form.html',
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

@recipes_bp.route('/stock/check', methods=['POST'])
@login_required
@require_permission('inventory.view')
def check_stock():
    """Check stock for a recipe using the recipe service (internally uses USCS)"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))

        if not recipe_id:
            return jsonify({"error": "Recipe ID is required"}), 400

        # Get recipe
        recipe = get_recipe_details(recipe_id)
        if not recipe:
            return jsonify({"error": "Recipe not found"}), 404

        # Use USCS directly
        from app.services.stock_check.core import UniversalStockCheckService
        uscs = UniversalStockCheckService()

        # Debug: Check if recipe has ingredients
        logger.info(f"STOCK_CHECK: Recipe {recipe_id} has {len(recipe.recipe_ingredients)} ingredients")
        for ri in recipe.recipe_ingredients:
            logger.info(f"STOCK_CHECK: - Ingredient {ri.inventory_item.name} (ID: {ri.inventory_item_id}), qty: {ri.quantity}, unit: {ri.unit}")

        result = uscs.check_recipe_stock(recipe_id, scale)

        # Process results for frontend
        if result.get('success'):
            stock_check = result.get('stock_check', [])
            # Convert USCS status values to frontend expected values
            for item in stock_check:
                if item.get('status') == 'needed':
                    item['status'] = 'NEEDED'
                elif item.get('status') == 'low':
                    item['status'] = 'LOW'
                elif item.get('status') == 'good':
                    item['status'] = 'OK'

                # Ensure frontend expected fields exist
                item['ingredient_name'] = item.get('item_name', item.get('ingredient_name', 'Unknown'))
                item['needed_amount'] = item.get('needed_quantity', 0)
                item['available_quantity'] = item.get('available_quantity', 0)
                item['unit'] = item.get('needed_unit', item.get('unit', ''))

            all_ok = all(item.get('status') not in ['NEEDED', 'INSUFFICIENT'] for item in stock_check)
            status = 'ok' if all_ok else 'insufficient'
        else:
            stock_check = result.get('stock_check', [])  # Include stock check data even on error
            all_ok = False
            status = 'error'

        return jsonify({
            "stock_check": stock_check,
            "status": status,
            "all_ok": all_ok,
            "recipe_name": recipe.name,
            "success": result.get('success', False),
            "error": result.get('error')
        }), 200
    except Exception as e:
        logger.error(f"Error in recipe stock check: {e}")
        return jsonify({"error": str(e)}), 500