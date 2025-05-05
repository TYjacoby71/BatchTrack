from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from models import db, Recipe, RecipeIngredient, InventoryItem, Unit
from utils.unit_utils import get_global_unit_list
from sqlalchemy.exc import SQLAlchemyError
from . import recipes_bp

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        try:
            # Create recipe first
            recipe = Recipe(
                name=request.form.get('name'),
                instructions=request.form.get('instructions'),
                label_prefix=request.form.get('label_prefix'),
                predicted_yield=float(request.form.get('predicted_yield') or 0.0),
                predicted_yield_unit=request.form.get('predicted_yield_unit') or "",
                requires_containers=True if request.form.get('requires_containers') else False,
                allowed_containers=[int(id) for id in request.form.getlist('allowed_containers')] if request.form.get('requires_containers') else []
            )
            db.session.add(recipe)
            db.session.flush()  # Get recipe.id before committing

            # Handle ingredients
            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amt, unit in zip(ingredient_ids, amounts, units):
                if ing_id and amt and unit:
                    try:
                        recipe_ingredient = RecipeIngredient(
                            recipe_id=recipe.id,
                            inventory_item_id=int(ing_id),
                            amount=float(amt.strip()),
                            unit=unit.strip()
                        )
                        db.session.add(recipe_ingredient)
                    except ValueError as e:
                        current_app.logger.error(f"Invalid ingredient data: {e}")
                        continue

            db.session.commit()
            flash('Recipe created successfully with ingredients.')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
        except ValueError as e:
            current_app.logger.error(f"Value error creating recipe: {str(e)}")
            flash('Invalid values in recipe form', 'error')
            db.session.rollback()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Database error creating recipe: {str(e)}")
            flash('Database error creating recipe', 'error')
            db.session.rollback()
        except Exception as e:
            current_app.logger.exception(f"Unexpected error creating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')
            db.session.rollback()


    inventory_units = get_global_unit_list()
    return render_template('recipe_form.html', recipe=None, all_ingredients=InventoryItem.query.all(), inventory_units=inventory_units)

@recipes_bp.route('/')
@login_required
def list_recipes():
    recipes = Recipe.query.all()
    inventory_units = get_global_unit_list()
    return render_template('recipe_list.html', recipes=recipes, inventory_units=inventory_units)

@recipes_bp.route('/<int:recipe_id>/view')
@login_required
def view_recipe(recipe_id):
    try:
        recipe = Recipe.query.get_or_404(recipe_id)
        inventory_units = get_global_unit_list()
        if not inventory_units:
            flash("Warning: No units found in system", "warning")
            inventory_units = []
        return render_template('view_recipe.html', 
                             recipe=recipe, 
                             inventory_units=inventory_units)
    except Exception as e:
        flash(f"Error loading recipe: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error viewing recipe: {str(e)}")
        return redirect(url_for('recipes.list_recipes'))

@recipes_bp.route('/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
def plan_production(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.parent_id:
        base_recipe = recipe.parent
    else:
        base_recipe = recipe

    allowed_containers = [
        {
            'id': c.id,
            'name': c.name,
            'storage_amount': c.storage_amount,
            'storage_unit': c.storage_unit
        }
        for c in InventoryItem.query.filter_by(type='container').all()
    ] if recipe.requires_containers else []
    
    inventory_units = get_global_unit_list()
    
    return render_template('plan_production.html', 
                         recipe=recipe,
                         base_recipe=base_recipe,
                         hide_variations=True,
                         allowed_containers=allowed_containers,
                         inventory_units=inventory_units)

@recipes_bp.route('/<int:recipe_id>/variation', methods=['GET', 'POST'])
@login_required
def create_variation(recipe_id):
    try:
        parent = Recipe.query.get_or_404(recipe_id)
        # Create variation object but don't save to database yet
        new_variation = Recipe(
            name=f"{parent.name} Variation",
            instructions=parent.instructions,
            label_prefix=parent.label_prefix,
            parent_id=parent.id
        )
        db.session.add(new_variation)
        db.session.flush()  # Get an ID for the new variation

        # Copy ingredients from parent
        for ingredient in parent.recipe_ingredients:
            new_ingredient = RecipeIngredient(
                recipe_id=new_variation.id,
                inventory_item_id=ingredient.inventory_item_id,
                amount=ingredient.amount,
                unit=ingredient.unit
            )
            db.session.add(new_ingredient)

        if request.method == 'POST':
            new_variation.name = request.form['name']
            new_variation.instructions = request.form.get('instructions', '')
            new_variation.label_prefix = request.form.get('label_prefix', '')

            # Clear existing ingredient links (important for updates)
            RecipeIngredient.query.filter_by(recipe_id=new_variation.id).delete()

            # Re-add ingredients from the form
            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amt, unit in zip(ingredient_ids, amounts, units):
                if ing_id and amt and unit:
                    try:
                        recipe_ingredient = RecipeIngredient(
                            recipe_id=new_variation.id,
                            inventory_item_id=int(ing_id),
                            amount=float(amt.strip()),
                            unit=unit.strip()
                        )
                        db.session.add(recipe_ingredient)
                    except ValueError as e:
                        current_app.logger.error(f"Invalid ingredient data: {e}")
                        flash(f"Invalid ingredient data: {e}", "error")
                        continue

            try:
                db.session.commit()
                flash('Recipe variation created successfully.')
                return redirect(url_for('recipes.view_recipe', recipe_id=new_variation.id))
            except SQLAlchemyError as e:
                current_app.logger.error(f"Database error saving variation: {str(e)}")
                flash('Database error saving variation', 'error')
                db.session.rollback()
            except Exception as e:
                current_app.logger.exception(f"Unexpected error saving variation: {str(e)}")
                flash('An unexpected error occurred saving variation', 'error')
                db.session.rollback()


        all_ingredients = InventoryItem.query.order_by(InventoryItem.name).all()
        inventory_units = get_global_unit_list()
        return render_template('recipe_form.html',
            recipe=new_variation,
            all_ingredients=all_ingredients,
            inventory_units=inventory_units,
            is_variation=True,
            parent_recipe=parent)
    except Exception as e:
        flash(f"Error creating variation: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error creating variation: {str(e)}")
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
    from flask_login import current_user

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
        unit = InventoryUnit(name=name, type=type)
        db.session.add(unit)
        db.session.commit()
        return jsonify({
            'name': unit.name,
            'type': unit.type
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    try:
        original = Recipe.query.get_or_404(recipe_id)
        ingredients = [(ri.inventory_item_id, ri.amount, ri.unit) for ri in original.recipe_ingredients]
        
        # Create new recipe without ingredients first
        new_recipe = Recipe(
            name=f"Copy of {original.name}",
            instructions=original.instructions,
            label_prefix=original.label_prefix,
            predicted_yield=original.predicted_yield,
            predicted_yield_unit=original.predicted_yield_unit,
            requires_containers=original.requires_containers,
            allowed_containers=original.allowed_containers.copy() if original.allowed_containers else []
        )
            
        return render_template('recipe_form.html',
                            recipe=new_recipe,
                            all_ingredients=InventoryItem.query.all(),
                            is_clone=True,
                            ingredient_prefill=ingredients,
                            inventory_units=get_global_unit_list())
    except Exception as e:
        flash(f"Error cloning recipe: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error cloning recipe: {str(e)}")
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    try:
        recipe = Recipe.query.get_or_404(recipe_id)

        # Start transaction
        db.session.begin_nested()

        try:
            # For variations, only delete the variation itself
            if recipe.parent_id:
                # Delete variation's ingredients
                RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()
                db.session.delete(recipe)
                flash('Variation deleted successfully.')
            else:
                # For main recipes, delete all variations first
                for variation in recipe.variations:
                    RecipeIngredient.query.filter_by(recipe_id=variation.id).delete()
                    db.session.delete(variation)

                # Then delete the main recipe
                RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()
                db.session.delete(recipe)
                flash('Recipe and all variations deleted successfully.')

            db.session.commit()

        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Database error deleting recipe {recipe_id}: {str(e)}")
            flash('Database error occurred while deleting recipe.', 'error')
            raise

    except Exception as e:
        current_app.logger.error(f"Error deleting recipe {recipe_id}: {str(e)}")
        flash('An error occurred while deleting the recipe.', 'error')

    return redirect(url_for('recipes.list_recipes'))

@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    if recipe.is_locked:
        flash('This recipe is locked and cannot be edited.', 'error')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))
    all_ingredients = InventoryItem.query.order_by(InventoryItem.name).all()
    inventory_units = get_global_unit_list()

    if request.method == 'POST':
        try:
            recipe.name = request.form['name']
            recipe.instructions = request.form.get('instructions', '')
            recipe.label_prefix = request.form.get('label_prefix', '')
            recipe.predicted_yield = float(request.form.get('predicted_yield') or 0.0)
            recipe.predicted_yield_unit = request.form.get('predicted_yield_unit') or ""
            recipe.requires_containers = True if request.form.get('requires_containers') else False
            recipe.allowed_containers = [int(id) for id in request.form.getlist('allowed_containers[]')] if request.form.get('requires_containers') else []

            # Clear existing ingredient links
            RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()

            # Re-add ingredients
            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amt, unit in zip(ingredient_ids, amounts, units):
                if ing_id and amt and unit:
                    try:
                        assoc = RecipeIngredient(
                            recipe_id=recipe.id,
                            inventory_item_id=int(ing_id),
                            amount=float(amt.strip()),
                            unit=unit.strip()
                        )
                        db.session.add(assoc)
                    except Exception as e:
                        current_app.logger.error(f"Error updating ingredient: {e}")
                        flash(f'Error updating ingredient: {str(e)}', 'error')

            db.session.commit()
            flash('Recipe updated successfully.')
            return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
        except ValueError as e:
            current_app.logger.error(f"Value error updating recipe: {str(e)}")
            flash('Invalid values in recipe form', 'error')
        except SQLAlchemyError as e:
            current_app.logger.error(f"Database error updating recipe: {str(e)}")
            flash('Database error updating recipe', 'error')
            db.session.rollback() # Rollback transaction on database error
        except Exception as e:
            current_app.logger.exception(f"Unexpected error updating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')
            db.session.rollback() # Rollback transaction on unexpected error

    return render_template('recipe_form.html', 
                         recipe=recipe,
                         all_ingredients=all_ingredients,
                         inventory_units=inventory_units, edit_mode=True)