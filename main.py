from flask import Flask, request, jsonify, render_template, redirect, Response
from datetime import datetime
import json
import os

app = Flask(__name__)

DATA_FILE = 'data.json'

import logging
logging.basicConfig(level=logging.INFO)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"ingredients": [], "recipes": [], "batches": [], "recipe_counter": 0, "batch_counter": 0}
    
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
        data.setdefault("ingredients", [])
        data.setdefault("recipes", [])
        data.setdefault("batches", [])
        data.setdefault("recipe_counter", len(data["recipes"]))
        data.setdefault("batch_counter", len(data["batches"]))
        return data

@app.route('/recipes/<int:recipe_id>')
def view_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        return "Recipe not found", 404
    return render_template('recipe_detail.html', recipe=recipe)

@app.route('/recipes/<int:recipe_id>/clone', methods=['POST'])
def clone_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    # Create new recipe with incremented ID
    new_recipe = recipe.copy()
    new_recipe['id'] = data["recipe_counter"] + 1
    data["recipe_counter"] = new_recipe['id']
    new_recipe['name'] = f"Copy of {recipe['name']}"
    new_recipe['ingredients'] = [ing.copy() for ing in recipe['ingredients']]

    data['recipes'].append(new_recipe)
    save_data(data)
    return redirect(f'/recipes/{new_recipe["id"]}')

@app.route('/recipes/<int:recipe_id>/edit', methods=['GET', 'POST'])
def edit_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    if request.method == 'POST':
        # Update recipe with form data
        recipe['name'] = request.form.get('name', '').strip()
        recipe['instructions'] = request.form.get('instructions', '').strip()

        # Get all ingredient name/quantity pairs
        names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('ingredient_quantity[]')
        units = request.form.getlist('ingredient_unit[]')

        recipe['ingredients'] = []
        for name, qty, unit in zip(names, quantities, units):
            if name and qty and unit:  # Only add if all fields are filled
                recipe['ingredients'].append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit
                })

        save_data(data)
        return redirect(f'/recipes/{recipe_id}')

    return render_template('recipe_edit.html', recipe=recipe)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/')
def index():
    data = load_data()
    stats = {
        'total_recipes': len(data['recipes']),
        'total_ingredients': len(data['ingredients']),
        'total_batches': len(data.get('batches', [])),
        'recent_batches': sorted(data.get('batches', []), key=lambda x: x['timestamp'], reverse=True)[:5]
    }
    return render_template('home.html', stats=stats)

@app.route('/low-stock')
def low_stock():
    data = load_data()
    threshold = 5  # Change this number as needed
    low_stock = []
    for item in data['ingredients']:
        try:
            if float(item.get('quantity', 0)) < threshold:
                low_stock.append(item)
        except ValueError:
            continue
    return render_template('low_inventory.html', low_stock=low_stock)

@app.route('/delete-ingredient/<string:name>', methods=['POST'])
def delete_ingredient(name):
    data = load_data()
    data['ingredients'] = [i for i in data['ingredients'] if i['name'] != name]
    save_data(data)
    return redirect('/ingredients')

@app.route('/restock-history')
def restock_history():
    data = load_data()
    return render_template('restock_history.html', restocks=data.get('restocks', []))

@app.route('/restock-ingredient/<string:name>', methods=['POST'])
def restock_ingredient(name):
    data = load_data()
    ingredient = next((i for i in data['ingredients'] if i['name'] == name), None)

    if not ingredient:
        return "Ingredient not found", 404

    added_qty = float(request.form.get('quantity', 0))
    current_qty = float(ingredient['quantity'])
    ingredient['quantity'] = str(current_qty + added_qty)

    restock_entry = {
        "ingredient": ingredient['name'],
        "amount": added_qty,
        "unit": ingredient['unit'],
        "date": datetime.utcnow().isoformat(),
        "source": request.form.get('source', 'Unknown'),
        "cost": request.form.get('cost', '0')
    }
    data.setdefault("restocks", []).append(restock_entry)
    save_data(data)
    return redirect('/ingredients')

@app.route('/edit-ingredient/<string:name>', methods=['GET', 'POST'])
def edit_ingredient(name):
    data = load_data()
    ingredient = next((i for i in data['ingredients'] if i['name'] == name), None)

    if not ingredient:
        return "Ingredient not found", 404

    if request.method == 'POST':
        ingredient['quantity'] = request.form.get('quantity', '').strip()
        ingredient['unit'] = request.form.get('unit', '').strip()
        ingredient['cost_per_unit'] = request.form.get('cost_per_unit', '0.00').strip()
        save_data(data)
        return redirect('/ingredients')

    return render_template('edit_ingredient.html', ingredient=ingredient, units=load_units())

@app.route('/ingredients/bulk-add', methods=['GET', 'POST'])
def bulk_add_ingredients():
    if request.method == 'POST':
        names = request.form.getlist('name[]')
        quantities = request.form.getlist('quantity[]')
        units = request.form.getlist('unit[]')

        data = load_data()
        for name, qty, unit in zip(names, quantities, units):
            if name and qty:  # Only add if name and quantity are provided
                data['ingredients'].append({
                    "name": name.strip(),
                    "quantity": qty.strip(),
                    "unit": unit.strip()
                })
        save_data(data)
        return redirect('/ingredients')
    return render_template('bulk_add_ingredients.html')

@app.route('/ingredients', methods=['GET'])
def list_ingredients():
    data = load_data()
    return render_template('ingredients.html', ingredients=data['ingredients'])


def load_units():
    with open('units.json', 'r') as f:
        return json.load(f)

@app.route('/add-ingredient', methods=['GET', 'POST'])
def add_ingredient():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        quantity = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', '').strip()

        if not name or not quantity:
            return "Name and quantity are required", 400

        data = load_data()
        cost_per_unit = request.form.get('cost_per_unit', '0.00').strip()
        new_ingredient = {
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "cost_per_unit": cost_per_unit
        }
        data['ingredients'].append(new_ingredient)
        save_data(data)
        return redirect('/ingredients')
    return render_template('add_ingredient.html', units=load_units())

@app.route('/recipes/new', methods=['GET', 'POST'])
def manage_recipes():
    if request.method == 'POST':
        data = load_data()
        recipe_name = request.form.get('name', '').strip()
        instructions = request.form.get('instructions', '').strip()
        recipe_id = data["recipe_counter"] + 1
        data["recipe_counter"] = recipe_id

        # Get all ingredient details from the form
        names = request.form.getlist('ingredient_name[]')
        quantities = request.form.getlist('ingredient_quantity[]')
        units = request.form.getlist('ingredient_unit[]')

        ingredients = []
        for name, qty, unit in zip(names, quantities, units):
            if name and qty and unit:  # Only add if all fields are filled
                ingredients.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit
                })

        new_recipe = {
            "id": recipe_id,
            "name": recipe_name or f"Recipe #{recipe_id}",
            "ingredients": ingredients,
            "instructions": instructions
        }

        data['recipes'].append(new_recipe)
        save_data(data)
        return redirect('/recipes')

    return render_template('add_recipe.html')


@app.route('/check-stock/<int:recipe_id>', methods=['GET'])
def check_stock(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404

    stock_check = []
    for item in recipe['ingredients']:
        ing = next((i for i in data['ingredients'] if i['name'].lower() == item['name'].lower()), None)
        if not ing or not ing.get('quantity'):
            stock_check.append({"ingredient": item['name'], "status": "Insufficient"})
            continue

        needed_qty = float(item['quantity'])
        available_qty = float(ing['quantity'])

        # Convert units if different
        if item.get('unit') and ing.get('unit') and item['unit'] != ing['unit']:
            converted_qty = convert_units(needed_qty, item['unit'], ing['unit'])
            if converted_qty is not None:
                needed_qty = converted_qty

        if available_qty < needed_qty:
            stock_check.append({"ingredient": item['name'], "status": "Insufficient"})
        else:
            stock_check.append({"ingredient": item['name'], "status": "OK"})

    return jsonify({"stock_check": stock_check})

@app.route('/check-stock-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()
    result = []

    if request.method == 'POST':
        demand = {}

        for recipe in data['recipes']:
            count = int(request.form.get(f"recipe_{recipe['id']}", 0))
            if count <= 0:
                continue
            for ing in recipe['ingredients']:
                name = ing['name']
                qty = float(ing['quantity']) * count
                unit = ing.get('unit', '')
                if name not in demand:
                    demand[name] = {'qty': 0, 'unit': unit}
                if unit == demand[name]['unit']:
                    demand[name]['qty'] += qty
                else:
                    converted_qty = convert_units(qty, unit, demand[name]['unit'])
                    if converted_qty is not None:
                        demand[name]['qty'] += converted_qty
                    else:
                        demand[name]['qty'] += qty

        for name, details in demand.items():
            match = next((i for i in data['ingredients'] if i['name'].lower() == name.lower()), None)
            if match and match.get('quantity'):
                available = float(match['quantity'])
                qty = details['qty']
                # Convert units if different
                if match.get('unit') and details['unit'] and match['unit'] != details['unit']:
                    converted_qty = convert_units(qty, details['unit'], match['unit'])
                    if converted_qty is not None:
                        qty = converted_qty
                to_order = round(max(qty - available, 0.0), 2)
            else:
                available = 0.0
                to_order = details['qty']
            result.append({
                "name": name,
                "needed": round(details['qty'], 2),
                "available": round(available, 2),
                "status": "Insufficient" if to_order > 0 else "OK",
                "unit": match['unit'] if match and match.get('unit') else details['unit']
            })

    if result:
        return render_template('stock_bulk_result.html', stock_report=result)
    return render_template('check_stock_bulk.html', recipes=data['recipes'])

@app.route('/recipes', methods=['GET'])
def list_recipes():
    data = load_data()
    return render_template('recipe_list.html', recipes=data['recipes'])

@app.route('/delete-recipe/<int:recipe_id>', methods=['POST'])
def delete_recipe(recipe_id):
    data = load_data()
    data['recipes'] = [r for r in data['recipes'] if r['id'] != recipe_id]
    save_data(data)
    return redirect('/recipes')


from unit_converter import convert_units, get_unit_type

@app.route('/start-batch/<int:recipe_id>', methods=['GET', 'POST'])
def start_batch(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    if request.method == 'POST':
        def to_float(val):
            try:
                return float(val.strip())
            except:
                return 0.0

        def check_inventory(recipe_item, inv_item):
            recipe_qty = to_float(recipe_item['quantity'])
            inv_qty = to_float(inv_item['quantity'])

            if recipe_item.get('unit') == inv_item.get('unit'):
                return inv_qty >= recipe_qty

            converted_qty = convert_units(recipe_qty, recipe_item['unit'], inv_item['unit'])
            if converted_qty is None:
                # fallback to raw comparison if units are unknown but match
                return inv_qty >= recipe_qty if recipe_item['unit'] == inv_item['unit'] else False
            return inv_qty >= converted_qty

        # Check inventory
        insufficient = []
        for item in recipe['ingredients']:
            inv_item = next((i for i in data['ingredients'] if i['name'].lower() == item['name'].lower()), None)
            if not inv_item:
                insufficient.append(item['name'])
                continue

            inv_qty = to_float(inv_item.get('quantity', 0))
            needed_qty = to_float(item.get('quantity', 0))

            # Convert units if different
            if item.get('unit') != inv_item.get('unit'):
                converted_qty = convert_units(needed_qty, item['unit'], inv_item['unit'])
                if converted_qty is not None:
                    needed_qty = converted_qty

            if inv_qty < needed_qty:
                insufficient.append(item['name'])

        if insufficient:
            return f"Insufficient stock for: {', '.join(insufficient)}", 400

        # Deduct inventory
        for item in recipe['ingredients']:
            for ing in data['ingredients']:
                if ing['name'].lower() == item['name'].lower():
                    ing_qty = to_float(ing['quantity'])
                    used_qty = to_float(item['quantity'])
                    
                    # Convert units if different
                    if item.get('unit') != ing.get('unit'):
                        converted_qty = convert_units(used_qty, item['unit'], ing['unit'])
                        if converted_qty is not None:
                            used_qty = converted_qty
                            
                    remaining = round(ing_qty - used_qty, 2)
                    ing['quantity'] = str(max(remaining, 0.0))  # No negative numbers

        # Handle notes + tags
        notes = request.form.get('notes', '').strip()
        tags_input = request.form.get('tags', '').strip()
        tags = [t.strip() for t in tags_input.split(',')] if tags_input else []

        data['batch_counter'] = data.get('batch_counter', 0) + 1
        batch_id = f"batch_{data['batch_counter']}"

        # Calculate total batch cost
        total_cost = 0.0
        for item in recipe['ingredients']:
            inv_item = next((i for i in data['ingredients'] if i['name'] == item['name']), None)
            if inv_item:
                cost = float(inv_item.get('cost_per_unit', 0)) * float(item['quantity'])
                total_cost += cost

        new_batch = {
            "id": batch_id,
            "recipe_id": recipe['id'],
            "recipe_name": recipe['name'],
            "timestamp": datetime.utcnow().isoformat(),
            "notes": notes,
            "tags": tags,
            "ingredients": recipe['ingredients'],
            "total_cost": round(total_cost, 2)
        }

        data.setdefault("batches", []).append(new_batch)
        save_data(data)
        return redirect('/batches')

    return render_template('start_batch.html', recipe=recipe)

@app.route('/download-purchase-list', methods=['POST'])
def download_purchase_list():
    import csv
    from io import StringIO

    data = request.json
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Ingredient', 'Needed', 'Available', 'To Order'])
    for item in data:
        writer.writerow([item['ingredient'], item['needed'], item['available'], item['to_order']])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=purchase_list.csv"}
    )

@app.route('/batches', methods=['GET'])
def view_batches():
    data = load_data()
    return render_template('batches.html', batches=data.get('batches', []))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)