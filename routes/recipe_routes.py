from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Recipe, Ingredient, RecipeIngredient, InventoryUnit
from flask import jsonify
from stock_check_utils import check_stock_for_recipe

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/', methods=['GET'])
@login_required
def list_recipes():
    recipes = Recipe.query.all()
    return render_template('recipe_list.html', recipes=recipes)

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    all_ingredients = Ingredient.query.order_by(Ingredient.name).all()
    if request.method == 'POST':
        try:
            recipe = Recipe(
                name=request.form['name'],
                instructions=request.form['instructions'],
                label_prefix=request.form['label_prefix']
            )

            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amount, unit in zip(ingredient_ids, amounts, units):
                if ing_id:
                    recipe_ingredient = RecipeIngredient(
                        ingredient_id=ing_id,
                        amount=float(amount),
                        unit=unit
                    )
                    recipe.recipe_ingredients.append(recipe_ingredient)

            db.session.add(recipe)
            db.session.commit()
            flash('Recipe created successfully')
            return redirect(url_for('recipes.list_recipes'))
        except Exception as e:
            flash(f'Error creating recipe: {str(e)}')
    else: #added else block for GET request
        all_ingredients = Ingredient.query.all()
        inventory_units = InventoryUnit.query.all()
        return render_template('recipe_form.html', recipe=None, all_ingredients=all_ingredients, inventory_units=inventory_units) #added inventory_units

@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
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
            db.session.commit()
            flash('Recipe updated successfully')
            return redirect(url_for('recipes.list_recipes'))
        except Exception as e:
            flash(f'Error updating recipe: {str(e)}')
            
    return render_template('recipe_form.html', recipe=recipe, all_ingredients=all_ingredients, inventory_units=inventory_units)


@recipes_bp.route('/units/quick-add', methods=['POST'])
@login_required
def quick_add_unit():
    data = request.get_json()
    name = data.get('name')
    
    try:
        unit = InventoryUnit(name=name, type='count')
        db.session.add(unit)
        db.session.commit()
        return jsonify({
            'id': unit.id,
            'name': unit.name,
            'type': 'count'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@recipes_bp.route('/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
def plan_production(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    scale = float(request.form.get('scale', 1.0)) if request.method == 'POST' else 1.0
    stock_check, all_ok = check_stock_for_recipe(recipe, scale)
    return render_template('plan_production.html', recipe=recipe, scale=scale,
                         stock_check=stock_check, all_ok=all_ok)