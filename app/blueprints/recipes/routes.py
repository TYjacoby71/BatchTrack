
from flask import render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from . import recipes_bp
from ...extensions import db
from ...models import Recipe, InventoryItem
from ...utils.permissions import require_permission
from ...services.recipe_service import (
    create_recipe, update_recipe, delete_recipe, get_recipe_details,
    plan_production, scale_recipe, validate_recipe_data, duplicate_recipe
)
from ...utils.unit_utils import get_global_unit_list
from ...models.unit import Unit
import logging

logger = logging.getLogger(__name__)

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        try:
            # Prepare ingredient data from form
            ingredients = []
            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amt, unit in zip(ingredient_ids, amounts, units):
                if ing_id and amt and unit:
                    try:
                        ingredients.append({
                            'item_id': int(ing_id),
                            'quantity': float(amt.strip()),
                            'unit': unit.strip()
                        })
                    except ValueError as e:
                        logger.error(f"Invalid ingredient data: {e}")
                        continue

            # Use recipe service to create recipe
            success, result = create_recipe(
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or "",
                ingredients=ingredients
            )

            if success:
                # Handle allowed containers separately (not in core service)
                recipe = result
                container_ids = [int(id) for id in request.form.getlist('allowed_containers[]') if id]
                recipe.allowed_containers = container_ids or []
                recipe.label_prefix = request.form.get('label_prefix')
                db.session.commit()
                
                flash('Recipe created successfully with ingredients.')
                return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
            else:
                flash(f'Error creating recipe: {result}', 'error')

        except Exception as e:
            logger.exception(f"Unexpected error creating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')

    # Get data for form
    ingredients_query = InventoryItem.query.filter(
        ~InventoryItem.type.in_(['product', 'product-reserved'])
    ).order_by(InventoryItem.name)

    if current_user.organization_id:
        ingredients_query = ingredients_query.filter_by(organization_id=current_user.organization_id)

    all_ingredients = ingredients_query.all()
    units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
    inventory_units = get_global_unit_list()
    
    return render_template('recipe_form.html', 
                         recipe=None, 
                         all_ingredients=all_ingredients, 
                         inventory_units=inventory_units, 
                         units=units)

@recipes_bp.route('/')
@login_required
def list_recipes():
    query = Recipe.query.filter_by(parent_id=None)

    if current_user.organization_id:
        query = query.filter_by(organization_id=current_user.organization_id)

    recipes = query.all()
    inventory_units = get_global_unit_list()
    return render_template('recipe_list.html', recipes=recipes, inventory_units=inventory_units)

@recipes_bp.route('/<int:recipe_id>/view')
@login_required
def view_recipe(recipe_id):
    try:
        recipe = get_recipe_details(recipe_id)
        if not recipe:
            flash('Recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))
            
        # Check organization access
        if not check_organization_access(Recipe, recipe_id):
            flash('Recipe not found or access denied.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        inventory_units = get_global_unit_list()
        return render_template('view_recipe.html', recipe=recipe, inventory_units=inventory_units)
        
    except Exception as e:
        flash(f"Error loading recipe: {str(e)}", "error")
        logger.exception(f"Unexpected error viewing recipe: {str(e)}")
        return redirect(url_for('recipes.list_recipes'))

@recipes_bp.route('/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
@require_permission('plan_production')
def plan_production_route(recipe_id):
    """Plan production for a recipe"""
    if not check_organization_access(Recipe, recipe_id):
        flash('Recipe not found or access denied.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    recipe = get_recipe_details(recipe_id)
    if not recipe:
        flash('Recipe not found.', 'error')
        return redirect(url_for('recipes.list_recipes'))

    if request.method == 'POST':
        try:
            data = request.get_json()
            scale = float(data.get('scale', 1.0))
            container_id = data.get('container_id')

            # Use recipe service for production planning
            planning_result = plan_production(recipe_id, scale, container_id)

            if planning_result['success']:
                # Format response for frontend
                stock_results = []
                for ingredient in planning_result['availability']['ingredients']:
                    stock_results.append({
                        'ingredient_id': ingredient['ingredient_id'],
                        'ingredient_name': ingredient['ingredient_name'],
                        'needed_amount': ingredient['required_quantity'],
                        'unit': ingredient['required_unit'],
                        'available': ingredient['is_available'],
                        'available_quantity': ingredient['available_quantity'],
                        'shortage': ingredient['shortage']
                    })

                return jsonify({
                    'success': True,
                    'stock_results': stock_results,
                    'all_available': planning_result['can_produce'],
                    'scale': scale,
                    'cost_info': planning_result['cost_info']
                })
            else:
                return jsonify({'success': False, 'error': planning_result['error']}), 500

        except Exception as e:
            logger.error(f"Error in production planning: {str(e)}")
            return jsonify({'success': False, 'error': 'Production planning failed'}), 500

    # GET request - show planning form
    return render_template('recipes/plan_production.html', recipe=recipe)

@recipes_bp.route('/<int:recipe_id>/variation', methods=['GET', 'POST'])
@login_required
def create_variation(recipe_id):
    try:
        parent = get_recipe_details(recipe_id)
        if not parent:
            flash('Parent recipe not found.', 'error')
            return redirect(url_for('recipes.list_recipes'))

        if request.method == 'POST':
            # Prepare ingredient data
            ingredients = []
            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amt, unit in zip(ingredient_ids, amounts, units):
                if ing_id and amt and unit:
                    try:
                        ingredients.append({
                            'item_id': int(ing_id),
                            'quantity': float(amt.strip()),
                            'unit': unit.strip()
                        })
                    except ValueError as e:
                        logger.error(f"Invalid ingredient data: {e}")
                        continue

            # Create variation using recipe service
            success, result = create_recipe(
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or parent.predicted_yield or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or parent.predicted_yield_unit or "",
                ingredients=ingredients
            )

            if success:
                # Set as variation and handle UI-specific fields
                variation = result
                variation.parent_id = parent.id
                variation.label_prefix = request.form.get('label_prefix')
                container_ids = [int(id) for id in request.form.getlist('allowed_containers[]') if id]
                variation.allowed_containers = container_ids or []
                db.session.commit()
                
                flash('Recipe variation created successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=variation.id))
            else:
                flash(f'Error creating variation: {result}', 'error')

        # GET - show variation form with parent data
        ingredients_query = InventoryItem.query.filter(
            ~InventoryItem.type.in_(['product', 'product-reserved'])
        ).order_by(InventoryItem.name)
        
        if current_user.organization_id:
            ingredients_query = ingredients_query.filter_by(organization_id=current_user.organization_id)
        
        all_ingredients = ingredients_query.all()
        units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
        
        # Create variation object for template
        new_variation = Recipe(
            name=f"{parent.name} Variation",
            instructions=parent.instructions,
            label_prefix=parent.label_prefix,
            parent_id=parent.id,
            predicted_yield=parent.predicted_yield,
            predicted_yield_unit=parent.predicted_yield_unit
        )

        return render_template('recipe_form.html',
                             recipe=new_variation,
                             all_ingredients=all_ingredients,
                             inventory_units=get_global_unit_list(),
                             units=units,
                             is_variation=True,
                             parent_recipe=parent)
                             
    except Exception as e:
        flash(f"Error creating variation: {str(e)}", "error")
        logger.exception(f"Unexpected error creating variation: {str(e)}")
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
            # Prepare ingredient data
            ingredients = []
            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units_list = request.form.getlist('units[]')

            for ing_id, amt, unit in zip(ingredient_ids, amounts, units_list):
                if ing_id and amt and unit:
                    try:
                        ingredients.append({
                            'item_id': int(ing_id),
                            'quantity': float(amt.strip()),
                            'unit': unit.strip()
                        })
                    except ValueError as e:
                        logger.error(f"Invalid ingredient data: {e}")
                        continue

            # Use recipe service to update
            success, result = update_recipe(
                recipe_id=recipe_id,
                name=request.form.get('name'),
                description=request.form.get('instructions'),
                instructions=request.form.get('instructions'),
                yield_amount=float(request.form.get('predicted_yield') or 0.0),
                yield_unit=request.form.get('predicted_yield_unit') or "",
                ingredients=ingredients
            )

            if success:
                # Handle UI-specific fields
                updated_recipe = result
                updated_recipe.label_prefix = request.form.get('label_prefix')
                container_ids = [int(id) for id in request.form.getlist('allowed_containers[]') if id]
                updated_recipe.allowed_containers = container_ids or []
                db.session.commit()
                
                flash('Recipe updated successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
            else:
                flash(f'Error updating recipe: {result}', 'error')

        except Exception as e:
            logger.exception(f"Unexpected error updating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')

    # GET - show edit form
    ingredients_query = InventoryItem.query.filter(
        ~InventoryItem.type.in_(['product', 'product-reserved'])
    ).order_by(InventoryItem.name)
    
    if current_user.organization_id:
        ingredients_query = ingredients_query.filter_by(organization_id=current_user.organization_id)
    
    all_ingredients = ingredients_query.all()
    units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()
    
    from ...models import Batch
    existing_batches = Batch.query.filter_by(recipe_id=recipe.id).count()

    return render_template('recipe_form.html',
                         recipe=recipe,
                         all_ingredients=all_ingredients,
                         inventory_units=get_global_unit_list(),
                         units=units,
                         edit_mode=True,
                         existing_batches=existing_batches)

@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    try:
        # Use recipe service to duplicate
        success, result = duplicate_recipe(recipe_id)
        
        if success:
            new_recipe = result
            # Prepare for editing
            ingredients = [(ri.inventory_item_id, ri.quantity, ri.unit) for ri in new_recipe.ingredients]

            ingredients_query = InventoryItem.query.filter(
                ~InventoryItem.type.in_(['product', 'product-reserved'])
            ).order_by(InventoryItem.name)
            
            if current_user.organization_id:
                ingredients_query = ingredients_query.filter_by(organization_id=current_user.organization_id)
            
            all_ingredients = ingredients_query.all()
            units = Unit.query.filter_by(is_active=True).order_by(Unit.unit_type, Unit.name).all()

            # Don't save to DB yet - let user edit first
            db.session.rollback()

            return render_template('recipe_form.html',
                                recipe=new_recipe,
                                all_ingredients=all_ingredients,
                                is_clone=True,
                                ingredient_prefill=ingredients,
                                inventory_units=get_global_unit_list(),
                                units=units)
        else:
            flash(f"Error cloning recipe: {result}", "error")
            
    except Exception as e:
        flash(f"Error cloning recipe: {str(e)}", "error")
        logger.exception(f"Unexpected error cloning recipe: {str(e)}")
        
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

@recipes_bp.route('/units/quick-add', methods=['POST'])
def quick_add_unit():
    data = request.get_json()
    name = data.get('name')
    type = data.get('type', 'volume')

    try:
        unit = Unit(name=name, type=type)
        db.session.add(unit)
        db.session.commit()
        return jsonify({
            'name': unit.name,
            'type': unit.type
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
