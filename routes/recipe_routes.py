
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Recipe, Ingredient, InventoryUnit, RecipeIngredient
from flask import jsonify
from stock_check_utils import check_stock_for_recipe

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/recipes')
@login_required
def list_recipes():
    recipes = Recipe.query.all()
    return render_template('recipe_list.html', recipes=recipes)

@recipes_bp.route('/recipes/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    all_ingredients = Ingredient.query.order_by(Ingredient.name).all()
    inventory_units = InventoryUnit.query.all()

    if request.method == 'POST':
        try:
            recipe = Recipe(
                name=request.form['name'],
                instructions=request.form['instructions'],
                label_prefix=request.form['label_prefix']
            )
            db.session.add(recipe)
            db.session.flush()  # Get recipe.id

            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amount, unit in zip(ingredient_ids, amounts, units):
                if ing_id:
                    assoc = RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_id=ing_id,
                        amount=float(amount),
                        unit=unit
                    )
                    db.session.add(assoc)

            db.session.commit()
            flash('Recipe created successfully.')
            return redirect(url_for('recipes.list_recipes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating recipe: {str(e)}')

    return render_template('recipe_form.html', recipe=None, all_ingredients=all_ingredients, inventory_units=inventory_units)

@recipes_bp.route('/recipes/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    all_ingredients = Ingredient.query.order_by(Ingredient.name).all()
    inventory_units = InventoryUnit.query.all()

    if request.method == 'POST':
        try:
            recipe.name = request.form['name']
            recipe.instructions = request.form['instructions']
            recipe.label_prefix = request.form['label_prefix']

            # Clear previous ingredients
            RecipeIngredient.query.filter_by(recipe_id=recipe.id).delete()

            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amount, unit in zip(ingredient_ids, amounts, units):
                if ing_id:
                    assoc = RecipeIngredient(
                        recipe_id=recipe.id,
                        ingredient_id=ing_id,
                        amount=float(amount),
                        unit=unit
                    )
                    db.session.add(assoc)

            db.session.commit()
            flash('Recipe updated successfully.')
            return redirect(url_for('recipes.list_recipes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating recipe: {str(e)}')

    return render_template('recipe_form.html', recipe=recipe, all_ingredients=all_ingredients, inventory_units=inventory_units)

@recipes_bp.route('/recipes/<int:recipe_id>/delete')
@login_required
def delete_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    db.session.delete(recipe)
    db.session.commit()
    flash('Recipe deleted.')
    return redirect(url_for('recipes.list_recipes'))
