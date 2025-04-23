from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, Recipe, RecipeIngredient, InventoryItem
from utils.unit_utils import get_global_unit_list
from stock_check_utils import check_stock_for_recipe
from sqlalchemy.exc import SQLAlchemyError

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/recipes')
@login_required
def list_recipes():
    recipes = Recipe.query.all()
    return render_template('recipe_list.html', recipes=recipes)

@recipes_bp.route('/<int:recipe_id>')
@login_required
def view_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    inventory_units = get_global_unit_list()
    return render_template('view_recipe.html', recipe=recipe, inventory_units=inventory_units)

@recipes_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_recipe():
    all_ingredients = InventoryItem.query.order_by(InventoryItem.name).all()
    inventory_units = get_global_unit_list()
    parent_recipes = Recipe.query.filter_by(parent_id=None).all()

    if request.method == 'POST':
        try:
            recipe = Recipe(
                name=request.form['name'],
                instructions=request.form['instructions'],
                label_prefix=request.form['label_prefix']
            )
            db.session.add(recipe)
            db.session.flush()

            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amount, unit in zip(ingredient_ids, amounts, units):
                if ing_id:
                    assoc = RecipeIngredient(
                        recipe_id=recipe.id,
                        inventory_item_id=ing_id,
                        amount=float(amount),
                        unit=unit
                    )
                    db.session.add(assoc)

            db.session.commit()
            flash('Recipe created successfully.')
            return redirect(url_for('recipes.list_recipes'))
        except (ValueError, KeyError) as e:
            db.session.rollback()
            flash(f"Invalid data: {str(e)}", "warning")
            return redirect(request.referrer or url_for('recipes.new_recipe'))

    return render_template('recipe_form.html', recipe=None, all_ingredients=all_ingredients, inventory_units=inventory_units, parent_recipes=parent_recipes)

@recipes_bp.route('/<int:recipe_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_recipe(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    all_ingredients = InventoryItem.query.order_by(InventoryItem.name).all()
    inventory_units = Unit.query.order_by(Unit.name).all()

    if request.method == 'POST':
        try:
            recipe.name = request.form['name']
            recipe.instructions = request.form['instructions']
            recipe.label_prefix = request.form['label_prefix']

            # Clear previous ingredients
            db.session.query(RecipeIngredient).filter_by(recipe_id=recipe.id).delete()

            ingredient_ids = request.form.getlist('ingredient_ids[]')
            amounts = request.form.getlist('amounts[]')
            units = request.form.getlist('units[]')

            for ing_id, amount, unit in zip(ingredient_ids, amounts, units):
                if ing_id:
                    assoc = RecipeIngredient(
                        recipe_id=recipe.id,
                        inventory_item_id=int(ing_id),
                        amount=float(amount),
                        unit=unit
                    )
                    db.session.add(assoc)

            db.session.commit()
            flash('Recipe updated successfully.')
            return redirect(url_for('recipes.edit_recipe', recipe_id=recipe.id))
        except (ValueError, KeyError) as e:
            db.session.rollback()
            flash(f"Invalid update data: {str(e)}", "warning")
            return redirect(request.referrer or url_for('recipes.edit_recipe', id=recipe_id))

    preselect_ingredient_id = session.pop('last_added_ingredient_id', None)
    add_ingredient_line = session.pop('add_ingredient_line', False)

    base_recipes = Recipe.query.filter_by(parent_id=None).all()
    units = Unit.query.all()
    parent_recipes = Recipe.query.filter_by(parent_id=None).all()

    return render_template('recipe_form.html',
        recipe=recipe,
        all_ingredients=all_ingredients,
        inventory_units=units,
        preselect_ingredient_id=preselect_ingredient_id,
        add_ingredient_line=add_ingredient_line,
        parent_recipes=parent_recipes,
        all_base_recipes=base_recipes
    )

@recipes_bp.route('/<int:recipe_id>/add-variation', methods=['GET', 'POST'])
@login_required
def add_variation(recipe_id):
    parent = Recipe.query.get_or_404(recipe_id)
    all_ingredients = InventoryItem.query.all()
    inventory_units = InventoryUnit.query.all()

    if request.method == 'POST':
        name = request.form.get('name')
        instructions = request.form.get('instructions')
        label_prefix = request.form.get('label_prefix')

        new_variation = Recipe(name=name, instructions=instructions, label_prefix=label_prefix, parent_id=parent.id)
        db.session.add(new_variation)
        db.session.flush()

        ingredient_ids = request.form.getlist('ingredient_ids[]')
        amounts = request.form.getlist('amounts[]')
        units = request.form.getlist('units[]')

        for ing_id, amount, unit in zip(ingredient_ids, amounts, units):
            if ing_id:
                assoc = RecipeIngredient(
                    recipe_id=new_variation.id,
                    inventory_item_id=int(ing_id),
                    amount=float(amount),
                    unit=unit
                )
                db.session.add(assoc)

        db.session.commit()
        flash("Variation created successfully.")
        return redirect(url_for('recipes.list_recipes'))

    return render_template(
        "recipe_form.html",
        recipe=None,
        all_ingredients=all_ingredients,
        inventory_units=inventory_units,
        is_variation=True,
        parent_recipe=parent
    )


# Delete route moved to blueprints/recipes/routes.py

@recipes_bp.route('/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
def plan_production(recipe_id):
    try:
        base_recipe = Recipe.query.get_or_404(recipe_id)
        variations = base_recipe.variations if base_recipe else []
        inventory_items = InventoryItem.query.all()
        containers = get_available_containers()

        recipe = base_recipe
        selected_variation_id = request.args.get('variation_id', type=int)
        if selected_variation_id:
            recipe = Recipe.query.get(selected_variation_id)

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
                recipe_check, ingredients_ok = check_stock_for_recipe(selected_recipe, scale)

                stock_check = recipe_check + container_check
                all_ok = ingredients_ok and containers_ok

                status = "ok" if all_ok else "bad"
                for item in stock_check:
                    if item["status"] == "LOW" and status != "bad":
                        status = "low"
            except ValueError as e:
                flash("Invalid scale value", "error")
                return redirect(url_for('recipes.plan_production', recipe_id=recipe_id))

    return render_template(
        'plan_production.html',
        recipe=recipe,
        variations=variations,
        scale=scale,
        stock_check=stock_check,
        all_ok=all_ok,
        status=status,
        inventory_items=inventory_items,
        containers=containers
    )

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

@recipes_bp.route('/<int:recipe_id>/clone', methods=['GET'])
@login_required
def clone_recipe(recipe_id):
    original = Recipe.query.get_or_404(recipe_id)
    cloned = Recipe(
        name=f"{original.name} Copy",
        instructions=original.instructions,
        label_prefix=original.label_prefix
    )
    db.session.add(cloned)
    db.session.flush()  # So it gets an ID before adding ingredients

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

@recipes_bp.route('/<int:recipe_id>/variation', methods=['GET'])
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