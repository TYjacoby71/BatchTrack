from flask import Blueprint, render_template, jsonify, request, redirect
from app.routes.utils import load_data, save_data

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/recipes')
def list_recipes():
    data = load_data()
    return render_template('recipe_list.html', recipes=data['recipes'])

@recipes_bp.route('/check-stock/<string:recipe_name>', methods=['GET'])
def check_stock(recipe_name):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['name'] == recipe_name), None)
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404

    stock_check = []
    for item in recipe['ingredients']:
        ing = next((i for i in data['ingredients'] if i['name'] == item['name']), None)
        if not ing or float(ing['quantity']) < float(item['quantity']):
            stock_check.append({"ingredient": item['name'], "status": "Insufficient"})
        else:
            stock_check.append({"ingredient": item['name'], "status": "OK"})

    return jsonify({"stock_check": stock_check})

@recipes_bp.route('/recipes')
def list_recipes():
    data = load_data()
    return render_template('recipe_list.html', recipes=data['recipes'])

@recipes_bp.route('/recipes/<int:recipe_id>')
def view_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        return "Recipe not found", 404
    return render_template('recipe_detail.html', recipe=recipe)

@recipes_bp.route('/recipes/<int:recipe_id>/edit', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    if request.method == 'POST':
        recipe['name'] = request.form.get('name', '').strip()
        recipe['instructions'] = request.form.get('instructions', '').strip()

        names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('ingredient_quantity[]')
        units = request.form.getlist('ingredient_unit[]')

        recipe['ingredients'] = []
        for name, qty, unit in zip(names, quantities, units):
            if name and qty and unit:
                recipe['ingredients'].append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit
                })

        save_data(data)
        return redirect(f'/recipes/{recipe_id}')

    return render_template('recipe_edit.html', recipe=recipe)

@recipes_bp.route('/recipes/<int:recipe_id>/delete')
def delete_recipe(recipe_id):
    data = load_data()
    data['recipes'] = [r for r in data['recipes'] if r['id'] != recipe_id]
    save_data(data)
    return redirect('/recipes')
def view_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        return "Recipe not found", 404
    return render_template('recipe_detail.html', recipe=recipe)

@recipes_bp.route('/recipes/<int:recipe_id>/clone', methods=['POST'])
def clone_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    new_recipe = recipe.copy()
    new_recipe['id'] = data['recipe_counter'] + 1
    data['recipe_counter'] = new_recipe['id']
    new_recipe['name'] = f"Copy of {recipe['name']}"
    new_recipe['ingredients'] = [ing.copy() for ing in recipe['ingredients']]
    data['recipes'].append(new_recipe)
    save_data(data)
    return redirect(f'/recipes/{new_recipe["id"]}')