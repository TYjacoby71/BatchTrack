from flask import Blueprint, render_template, jsonify, request, redirect
from app.routes.utils import load_data, save_data
from unit_converter import check_stock_availability, UnitConversionService
import json

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/recipes')
def list_recipes():
    data = load_data()
    tags = set()
    for r in data["recipes"]:
        for t in r.get("tags", []):
            tags.add(t.lower())
    return render_template('recipe_list.html', recipes=data['recipes'], all_tags=sorted(tags))

@recipes_bp.route('/api/check-stock/<string:recipe_name>', methods=['GET'])
def check_stock_api(recipe_name):
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
        recipe['name'] = request.form['name']
        recipe['instructions'] = request.form['instructions']

        # Handle ingredients
        ingredients = []
        names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('ingredient_quantity[]')
        units = request.form.getlist('ingredient_unit[]')

        for name, qty, unit in zip(names, quantities, units):
            if name and qty:
                ingredients.append({
                    'name': name,
                    'quantity': float(qty),
                    'unit': unit
                })

        recipe['ingredients'] = ingredients
        save_data(data)
        return redirect(f'/recipes/{recipe_id}')

    with open('units.json') as f:
        units = json.load(f)
    all_ingredients = data['ingredients']
    return render_template('recipe_edit.html', 
                         recipe=recipe,
                         ingredients=all_ingredients,
                         units=units)


# Stock check route moved to stock blueprint
def check_stock(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        return "Recipe not found", 404

    from app.unit_conversion import check_stock_availability, converter

    stock_check = []
    for item in recipe['ingredients']:
        ing = next((i for i in data['ingredients'] if i['name'].lower() == item['name'].lower()), None)

        if ing:
            available, converted_stock, needed = check_stock_availability(
                float(item.get('quantity', 0)), 
                item.get('unit', 'units'),
                float(ing.get('quantity', 0)),
                ing.get('unit', 'units')
            )
            
            status = "OK" if available else "LOW"
            stock_check.append({
                "name": item['name'],
                "needed": float(item.get('quantity', 0)),
                "available": converted_stock,
                "unit": item.get('unit', 'units'),
                "status": status
            })
        else:
            stock_check.append({
                "name": item['name'],
                "needed": float(item.get('quantity', 0)),
                "available": 0,
                "unit": item.get('unit', 'units'),
                "status": "LOW"
            })

    return render_template('single_recipe_stock.html', recipe=recipe, stock_check=stock_check)

@recipes_bp.route('/recipes/<int:recipe_id>/delete', methods=['GET', 'POST'])
def delete_recipe(recipe_id):
    data = load_data()
    data['recipes'] = [r for r in data['recipes'] if r['id'] != recipe_id]
    save_data(data)
    return redirect('/recipes')

@recipes_bp.route('/recipes/new', methods=['GET', 'POST'])
def new_recipe():
    if request.method == 'POST':
        data = load_data()
        product_type = request.form.get('product_type')
        if product_type == '__custom__':
            product_type = request.form.get('custom_product_type')

        use_area = request.form.get('use_area')
        if use_area == '__custom__':
            use_area = request.form.get('custom_use_area')

        use_case = request.form.get('use_case')
        if use_case == '__custom__':
            use_case = request.form.get('custom_use_case')

        new_recipe = {
            'id': data.get('recipe_counter', 0) + 1,
            'name': request.form['name'],
            'description': request.form.get('description', ''),
            'instructions': request.form['instructions'],
            'tags': [t.strip().lower() for t in request.form.get('tags', '').split(',') if t.strip()],
            'product_type': product_type,
            'use_area': use_area,
            'use_case': use_case,
            'primary_ingredient': request.form.get('primary_ingredient', ''),
            'ingredients': []
        }

        names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('ingredient_quantity[]')
        units = request.form.getlist('ingredient_unit[]')

        for name, qty, unit in zip(names, quantities, units):
            if name and qty:
                new_recipe['ingredients'].append({
                    'name': name,
                    'quantity': qty,
                    'unit': unit
                })

        data['recipe_counter'] = new_recipe['id']
        data['recipes'].append(new_recipe)
        save_data(data)
        return redirect(f'/recipes/{new_recipe["id"]}')

    data = load_data()
    with open('units.json') as f:
        units = json.load(f)
    return render_template('recipe_edit.html', 
                         recipe={'name': '', 'instructions': '', 'ingredients': []}, 
                         ingredients=data['ingredients'],
                         recipe_only_ingredients=data.get('recipe_only_ingredients', []),
                         units=units)

@recipes_bp.route('/recipes/<int:recipe_id>/clone', methods=['GET', 'POST'])
def clone_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    if request.method == 'GET':
        new_recipe = recipe.copy()
        new_recipe['id'] = None  # Mark as new for template
        new_recipe['name'] = f"Copy of {recipe['name']}"
        new_recipe['ingredients'] = [ing.copy() for ing in recipe['ingredients']]
        return render_template('recipe_edit.html', 
                             recipe=new_recipe,
                             ingredients=data['ingredients'],
                             recipe_only_ingredients=data.get('recipe_only_ingredients', []),
                             is_clone=True)

    # POST handling remains the same as new recipe creation
    new_recipe = {
        'id': data.get('recipe_counter', 0) + 1,
        'name': request.form['name'],
        'description': request.form.get('description', ''),
        'instructions': request.form['instructions'],
        'ingredients': []
    }

    names = request.form.getlist('ingredient_name[]')
    quantities = request.form.getlist('ingredient_quantity[]')
    units = request.form.getlist('ingredient_unit[]')

    for name, qty, unit in zip(names, quantities, units):
        if name and qty:
            new_recipe['ingredients'].append({
                'name': name,
                'quantity': qty,
                'unit': unit
            })

    data['recipe_counter'] = new_recipe['id']
    data['recipes'].append(new_recipe)
    save_data(data)
    return redirect(f'/recipes/{new_recipe["id"]}')


@recipes_bp.route('/recipes/plan/<int:recipe_id>', methods=['GET', 'POST'])
def plan_production(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        return "Recipe not found", 404

    scale = float(request.args.get('scale', 1))
    stock_check = []
    missing_items = {}
    inventory = data.get('ingredients', [])
    
    if request.method == 'POST':
        scale = float(request.form.get('scale', 1))
        if 'start_batch' in request.form:
            return redirect(f'/start-batch/{recipe_id}?scale={scale}')
        
        if 'check_stock' in request.form:
            for item in recipe.get('ingredients', []):
        name = item['name']
        needed_qty = float(item['quantity']) * scale
        unit = item.get('unit', 'units')

        match = next((i for i in inventory if i['name'].lower() == name.lower()), None)
        if match:
            try:
                check = check_stock_availability(
                    needed_qty, unit,
                    float(match['quantity']), match['unit'],
                    material=name.lower()
                )
                if check['status'] == 'LOW':
                    missing_items[name] = {
                        'needed': needed_qty,
                        'available': check['converted'],
                        'unit': unit
                    }
                stock_check.append({
                    'name': name,
                    'needed': f"{needed_qty} {unit}",
                    'available': f"{check['converted']} {check['unit']}",
                    'status': check['status']
                })
            except (ValueError, TypeError):
                stock_check.append({
                    'name': name,
                    'needed': f"{needed_qty} {unit}",
                    'available': "0",
                    'status': 'LOW'
                })
                missing_items[name] = {
                    'needed': needed_qty,
                    'available': 0,
                    'unit': unit
                }
        else:
            stock_check.append({
                'name': name,
                'needed': f"{needed_qty} {unit}",
                'available': "0",
                'status': 'LOW'
            })
            missing_items[name] = {
                'needed': needed_qty,
                'available': 0,
                'unit': unit
            }

    return render_template('plan_production.html', 
                         recipe=recipe,
                         scale=scale,
                         stock_check=stock_check,
                         missing_items=missing_items)
