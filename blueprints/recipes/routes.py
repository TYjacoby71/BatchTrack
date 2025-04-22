
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Recipe, RecipeIngredient, InventoryItem, Unit

recipes_bp = Blueprint('recipes', __name__)

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
        return redirect(url_for('recipes.edit_recipe', recipe_id=recipe.id))
    return render_template('recipes/edit.html', recipe=None, all_ingredients=InventoryItem.query.all(), units=Unit.query.all())

@recipes_bp.route('/')
@login_required
def list_recipes():
    recipes = Recipe.query.filter_by(parent_id=None).all()
    return render_template('recipe_list.html', recipes=recipes)

@recipes_bp.route('/<int:recipe_id>/view')
@login_required
def view_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template('view_recipe.html', recipe=recipe)

@recipes_bp.route('/<int:recipe_id>/plan')
@login_required
def plan_production(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template('plan_production.html', recipe=recipe)

@recipes_bp.route('/<int:recipe_id>/variation')
@login_required
def create_variation(recipe_id):
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

@recipes_bp.route('/<int:recipe_id>/lock', methods=['POST'])
@login_required
def lock_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    recipe.is_locked = True
    db.session.commit()
    flash('Recipe locked.')
    return redirect(url_for('recipes.view_recipe', recipe_id=recipe.id))

@recipes_bp.route('/<int:recipe_id>/clone')
@login_required
def clone_recipe(recipe_id):
    original = Recipe.query.get_or_404(recipe_id)
    clone = Recipe(
        name=f"Copy of {original.name}",
        instructions=original.instructions,
        label_prefix=original.label_prefix
    )
    db.session.add(clone)
    db.session.flush()

    for ingredient in original.recipe_ingredients:
        new_ingredient = RecipeIngredient(
            recipe_id=clone.id,
            inventory_item_id=ingredient.inventory_item_id,
            amount=ingredient.amount,
            unit=ingredient.unit
        )
        db.session.add(new_ingredient)

    db.session.commit()
    flash('Recipe cloned successfully')
    return redirect(url_for('recipes.edit_recipe', recipe_id=clone.id))

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
