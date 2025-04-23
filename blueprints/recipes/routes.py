
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Recipe, RecipeIngredient

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/')
@login_required
def list_recipes():
    recipes = Recipe.query.all()
    return render_template('recipe_list.html', recipes=recipes)

@recipes_bp.route('/<int:recipe_id>')
@login_required
def view_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template('view_recipe.html', recipe=recipe)

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    if request.method == 'POST':
        recipe = Recipe(
            name=request.form.get('name'),
            instructions=request.form.get('instructions'),
            label_prefix=request.form.get('label_prefix')
        )
        db.session.add(recipe)
        db.session.commit()
        flash('Recipe created successfully.')
        return redirect(url_for('recipes.list_recipes'))
    return render_template('recipe_form.html', recipe=None)

@recipes_bp.route('/<int:recipe_id>/variation/new')
@login_required
def create_variation(recipe_id):
    parent = Recipe.query.get_or_404(recipe_id)
    variation = Recipe(
        name=f"{parent.name} Variation",
        instructions=parent.instructions,
        label_prefix=parent.label_prefix,
        parent_id=parent.id
    )
    db.session.add(variation)
    db.session.flush()

    for assoc in parent.recipe_ingredients:
        new_assoc = RecipeIngredient(
            recipe_id=variation.id,
            inventory_item_id=assoc.inventory_item_id,
            amount=assoc.amount,
            unit=assoc.unit
        )
        db.session.add(new_assoc)

    db.session.commit()
    flash("Variation created.")
    return redirect(url_for('recipes.edit_recipe', recipe_id=variation.id))

@recipes_bp.route('/<int:recipe_id>/lock', methods=['POST'])
@login_required
def lock_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.is_locked = True
    db.session.commit()
    flash('Recipe locked.')
    return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))

@recipes_bp.route('/<int:recipe_id>/unlock', methods=['POST'])
@login_required
def unlock_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    unlock_password = request.form.get('password')
    
    # Replace this with your actual password verification
    if unlock_password == 'admin123':  # You should use a secure password and proper hashing
        recipe.is_locked = False
        db.session.commit()
        flash('Recipe unlocked successfully.')
    else:
        flash('Invalid password.', 'error')
        
    return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))
