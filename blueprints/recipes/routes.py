
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required
from models import db, Recipe, RecipeIngredient, InventoryItem, Unit, InventoryUnit
from utils.unit_utils import get_global_unit_list
from stock_check_utils import check_recipe_stock, check_container_availability
from sqlalchemy.exc import SQLAlchemyError

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/')
@login_required
def list_recipes():
    recipes = Recipe.query.filter_by(parent_id=None).all()
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

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        try:
            recipe = Recipe(
                name=request.form.get('name'),
                instructions=request.form.get('instructions'),
                label_prefix=request.form.get('label_prefix')
            )
            db.session.add(recipe)
            db.session.flush()

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
            flash('Recipe created successfully.')
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
    return render_template('recipe_form.html', 
                         recipe=None, 
                         all_ingredients=InventoryItem.query.all(), 
                         inventory_units=inventory_units)

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

            RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()

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
            db.session.rollback()
        except SQLAlchemyError as e:
            current_app.logger.error(f"Database error updating recipe: {str(e)}")
            flash('Database error updating recipe', 'error')
            db.session.rollback()
        except Exception as e:
            current_app.logger.exception(f"Unexpected error updating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')
            db.session.rollback()

    return render_template('recipe_form.html', 
                         recipe=recipe,
                         all_ingredients=all_ingredients,
                         inventory_units=inventory_units,
                         edit_mode=True)

@recipes_bp.route('/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
def plan_production(recipe_id):
    try:
        base_recipe = Recipe.query.get_or_404(recipe_id)
        # If it's a variation, use that directly
        if base_recipe.parent_id:
            recipe = base_recipe
            base_recipe = recipe.parent
        else:
            recipe = base_recipe
            
        containers = InventoryItem.query.filter_by(type='container').all()
        containers = containers or []  # Ensure containers is never None

        scale = 1.0
        stock_check = []
        all_ok = False
        status = None

        if request.method == 'POST':
            try:
                scale = float(request.form.get('scale', 1.0))
                selected_id = request.form.get('variation_id') or recipe.id
                selected_recipe = Recipe.query.get(selected_id)

                # Process container selections
                container_ids = request.form.getlist('container_ids[]')
                container_check, containers_ok = check_container_availability(container_ids, scale)
                recipe_check, ingredients_ok = check_recipe_stock(selected_recipe, scale)

                stock_check = recipe_check + container_check
                all_ok = ingredients_ok and containers_ok

                status = "ok" if all_ok else "bad"
                for item in stock_check:
                    if item["status"] == "LOW" and status != "bad":
                        status = "low"
            except ValueError as e:
                flash("Invalid scale value", "error")
                return redirect(url_for('recipes.plan_production', recipe_id=recipe_id))

        return render_template('plan_production.html',
                            recipe=recipe,
                            base_recipe=base_recipe,
                            scale=scale,
                            stock_check=stock_check,
                            all_ok=all_ok,
                            status=status,
                            containers=containers)
    except Exception as e:
        flash(f"Error planning production: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error in plan_production: {str(e)}")
        return redirect(url_for('recipes.list_recipes'))

@recipes_bp.route('/<int:recipe_id>/variation', methods=['GET', 'POST'])
@login_required
def create_variation(recipe_id):
    try:
        parent = Recipe.query.get_or_404(recipe_id)
        variation = Recipe(
            name=f"{parent.name} Variation",
            instructions=parent.instructions,
            label_prefix=parent.label_prefix,
            parent_id=parent.id
        )
        db.session.add(variation)
        db.session.flush()

        for ingredient in parent.recipe_ingredients:
            new_ingredient = RecipeIngredient(
                recipe_id=variation.id,
                inventory_item_id=ingredient.inventory_item_id,
                amount=ingredient.amount,
                unit=ingredient.unit
            )
            db.session.add(new_ingredient)

        if request.method == 'POST':
            variation.name = request.form['name']
            variation.instructions = request.form.get('instructions', '')
            variation.label_prefix = request.form.get('label_prefix', '')

            RecipeIngredient.query.filter_by(recipe_id=variation.id).delete()

            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amt, unit in zip(ingredient_ids, amounts, units):
                if ing_id and amt and unit:
                    try:
                        recipe_ingredient = RecipeIngredient(
                            recipe_id=variation.id,
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
                return redirect(url_for('recipes.view_recipe', recipe_id=variation.id))
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
            recipe=variation,
            all_ingredients=all_ingredients,
            inventory_units=inventory_units,
            is_variation=True,
            parent_recipe=parent)
    except Exception as e:
        flash(f"Error creating variation: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error creating variation: {str(e)}")
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))

@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    try:
        original = Recipe.query.get_or_404(recipe_id)
        cloned = Recipe(
            name=f"{original.name} Copy",
            instructions=original.instructions,
            label_prefix=original.label_prefix
        )
        db.session.add(cloned)
        db.session.flush()

        for assoc in original.recipe_ingredients:
            new_assoc = RecipeIngredient(
                recipe_id=cloned.id,
                inventory_item_id=assoc.inventory_item_id,
                amount=assoc.amount,
                unit=assoc.unit
            )
            db.session.add(new_assoc)

        db.session.commit()
        flash("Recipe duplicated.")
        return redirect(url_for('recipes.edit_recipe', recipe_id=cloned.id))
    except Exception as e:
        flash(f"Error cloning recipe: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error cloning recipe: {str(e)}")
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

@recipes_bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    try:
        recipe = Recipe.query.get_or_404(recipe_id)
        db.session.begin_nested()

        try:
            if recipe.parent_id:
                RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()
                db.session.delete(recipe)
                flash('Variation deleted successfully.')
            else:
                for variation in recipe.variations:
                    RecipeIngredient.query.filter_by(recipe_id=variation.id).delete()
                    db.session.delete(variation)
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
