from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from models import db, Recipe, RecipeIngredient, InventoryItem, Unit
from utils.unit_utils import get_global_unit_list
from sqlalchemy.exc import SQLAlchemyError


recipes_bp = Blueprint('recipes', __name__)

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
            db.session.commit()
            flash('Recipe created successfully.')
            return redirect(url_for('recipes.edit_recipe', recipe_id=recipe.id))
        except ValueError as e:
            current_app.logger.error(f"Value error creating recipe: {str(e)}")
            flash('Invalid values in recipe form', 'error')
        except SQLAlchemyError as e:
            current_app.logger.error(f"Database error creating recipe: {str(e)}")
            flash('Database error creating recipe', 'error')
            db.session.rollback() # Rollback transaction on database error
        except Exception as e:
            current_app.logger.exception(f"Unexpected error creating recipe: {str(e)}")
            flash('An unexpected error occurred', 'error')
            db.session.rollback() # Rollback transaction on unexpected error


    inventory_units = get_global_unit_list()
    return render_template('recipe_form.html', recipe=None, all_ingredients=InventoryItem.query.all(), inventory_units=inventory_units)

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

@recipes_bp.route('/<int:recipe_id>/plan')
@login_required
def plan_production(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template('plan_production.html', recipe=recipe)

@recipes_bp.route('/<int:recipe_id>/variation')
@login_required
def create_variation(recipe_id):
    try:
        original = Recipe.query.get_or_404(recipe_id)
        variation = Recipe(
            name=f"Variation of {original.name}",
            instructions=original.instructions,
            label_prefix=original.label_prefix,
            parent_id=original.id
        )
        db.session.add(variation)
        db.session.flush()

        for ingredient in original.recipe_ingredients:
            new_ingredient = RecipeIngredient(
                recipe_id=variation.id,
                inventory_item_id=ingredient.inventory_item_id,
                amount=ingredient.amount,
                unit=ingredient.unit
            )
            db.session.add(new_ingredient)

        db.session.commit()
        flash('Variation created successfully')
        return redirect(url_for('recipes.edit_recipe', recipe_id=variation.id))
    except Exception as e:
        flash(f"Error creating variation: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error creating variation: {str(e)}")
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))



@recipes_bp.route('/<int:recipe_id>/delete', methods=['POST'])
@login_required
def delete_recipe(recipe_id):
    try:
        recipe = Recipe.query.get_or_404(recipe_id)
        db.session.delete(recipe)
        db.session.commit()
        flash('Recipe deleted successfully.')
        return redirect(url_for('recipes.list_recipes'))
    except Exception as e:
        flash(f"Error deleting recipe: {str(e)}", "error")
        return redirect(url_for('recipes.edit_recipe', recipe_id=recipe_id))

@recipes_bp.route('/<int:recipe_id>/lock', methods=['POST'])
@login_required
def lock_recipe(recipe_id):
    try:
        recipe = Recipe.query.get_or_404(recipe_id)
        recipe.is_locked = True
        db.session.commit()
        flash('Recipe locked.')
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
    except Exception as e:
        flash(f"Error locking recipe: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error locking recipe: {str(e)}")
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    try:
        original = Recipe.query.get_or_404(recipe_id)
        clone = Recipe(
            name=f"Copy of {original.name}",
            instructions=original.instructions,
            label_prefix=original.label_prefix
        )
        db.session.add(clone)
        db.session.flush()

        # Clone all recipe ingredients with exact amounts and units
        for assoc in original.recipe_ingredients:
            new_assoc = RecipeIngredient(
                recipe_id=clone.id,
                inventory_item_id=assoc.inventory_item_id,
                amount=assoc.amount,
                unit=assoc.unit
            )
            db.session.add(new_assoc)

        db.session.commit()
        flash('Recipe and ingredients cloned successfully')
        return redirect(url_for('recipes.edit_recipe', recipe_id=clone.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Error cloning recipe: {str(e)}", "error")
        current_app.logger.exception(f"Unexpected error cloning recipe: {str(e)}")
        return redirect(url_for('recipes.view_recipe', recipe_id=recipe_id))


@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    all_ingredients = InventoryItem.query.order_by(InventoryItem.name).all()
    inventory_units = get_global_unit_list()

    if request.method == 'POST':
        try:
            recipe.name = request.form.get('name')
            recipe.instructions = request.form.get('instructions')
            recipe.label_prefix = request.form.get('label_prefix')
            db.session.commit()
            flash('Recipe updated successfully.')
            return redirect(url_for('recipes.list_recipes'))
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
                         inventory_units=inventory_units)