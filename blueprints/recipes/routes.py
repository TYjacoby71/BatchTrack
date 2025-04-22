
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Recipe, RecipeIngredient, InventoryItem, Unit

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/')
@login_required
def list_recipes():
    recipes = Recipe.query.filter_by(parent_id=None).all()
    return render_template('recipe_list.html', recipes=recipes)

@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    all_ingredients = InventoryItem.query.order_by(InventoryItem.name).all()
    units = Unit.query.order_by(Unit.name).all()
    
    if request.method == 'POST':
        try:
            recipe.name = request.form.get('name')
            recipe.instructions = request.form.get('instructions')
            recipe.label_prefix = request.form.get('label_prefix')
            db.session.commit()
            flash('Recipe updated successfully.')
            return redirect(url_for('recipes.list_recipes'))
        except Exception as e:
            flash(f'Error updating recipe: {str(e)}')
            
    return render_template('recipes/edit.html', 
                         recipe=recipe,
                         all_ingredients=all_ingredients,
                         units=units)
