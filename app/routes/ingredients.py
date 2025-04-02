from flask import Blueprint, render_template, request, redirect
from app.routes.utils import load_data, save_data
from app.routes.faults import log_fault
from datetime import datetime
import json
from collections import defaultdict

ingredients_bp = Blueprint('ingredients', __name__)

@ingredients_bp.route('/home')
def index():
    data = load_data()
    stats = {
        'total_recipes': len(data.get('recipes', [])),
        'total_ingredients': len(data.get('ingredients', [])),
        'total_batches': len(data.get('batches', [])),
        'recent_batches': sorted(data.get('batches', []), 
                               key=lambda x: x['timestamp'], 
                               reverse=True)[:5]
    }
    return render_template('home.html', stats=stats)

@ingredients_bp.route('/ingredients')
def ingredients():
    data = load_data()
    return render_template('ingredients.html', ingredients=data['ingredients'])

@ingredients_bp.route('/ingredients/bulk-update', methods=['POST'])
def bulk_update_ingredients():
    from datetime import datetime
    data = load_data()
    ingredients = data.get("ingredients", [])
    action = request.form.get("action")

    if action == "delete":
        to_delete = request.form.getlist("delete")
        ingredients = [i for i in ingredients if i["name"] not in to_delete]

    elif action == "update":
        for i in ingredients:
            name = i["name"]
            unit = i["unit"]
            delta_key = f"delta_{name}"
            reason_key = f"reason_{name}"

            if delta_key in request.form:
                try:
                    delta = float(request.form[delta_key])
                    i["quantity"] = float(i.get("quantity", 0)) + delta

                    data.setdefault("inventory_log", []).append({
                        "name": name,
                        "change": delta,
                        "unit": unit,
                        "reason": request.form.get(reason_key, "Unspecified"),
                        "timestamp": datetime.now().isoformat()
                    })
                except ValueError as e:
                    log_fault(f"Value Error during bulk update: {e}")
                    continue

    data["ingredients"] = ingredients
    save_data(data)
    return redirect("/ingredients")

@ingredients_bp.route('/add', methods=['GET', 'POST'])
@ingredients_bp.route('/add-ingredient', methods=['GET', 'POST'])
def add_ingredient():
    if request.method == 'POST':
        data = load_data()
        new_ingredient = {
            'name': request.form['name'],
            'quantity': request.form['quantity'],
            'unit': request.form['unit'],
            'cost_per_unit': request.form.get('cost_per_unit', '0.00')
        }
        data['ingredients'].append(new_ingredient)
        save_data(data)
        redirect_url = request.form.get('next') or '/ingredients'
        return redirect(redirect_url)
    next_url = request.args.get('next', '')
    return render_template('edit_ingredient.html', ingredient=None, next=next_url)

@ingredients_bp.route('/stock/edit-ingredient/<name>', methods=['GET', 'POST'])
def edit_ingredient(name):
    data = load_data()
    ingredient = next((i for i in data['ingredients'] if i['name'] == name), None)
    if not ingredient:
        return "Ingredient not found", 404

    if request.method == 'POST':
        new_name = request.form['name']
        # Update name in ingredient list
        ingredient['name'] = new_name
        quantity = request.form.get('quantity', '')
        try:
            quantity = float(quantity) if quantity else 0
            if quantity < 0:
                flash("Quantity cannot be negative")
                return redirect(url_for('ingredients.ingredients'))
        except ValueError as e:
            log_fault(f"Value Error during edit: {e}")
            quantity = 0
        ingredient['quantity'] = quantity
        ingredient['unit'] = request.form['unit']
        ingredient['cost_per_unit'] = request.form.get('cost_per_unit', '0.00')
        save_data(data)
        return redirect('/ingredients')

    return render_template('edit_ingredient.html', ingredient=ingredient)

@ingredients_bp.route('/delete-ingredient/<name>', methods=['POST'])
def delete_ingredient(name):
    data = load_data()
    data['ingredients'] = [i for i in data['ingredients'] if i['name'] != name]
    save_data(data)
    return redirect('/ingredients')



@ingredients_bp.route('/quickadd', methods=['GET', 'POST'])
def quick_add_ingredient():
    if request.method == 'POST':
        data = load_data()
        name = request.form['name']
        unit = request.form['unit']

        # Only add if it doesn't exist in either list
        if not any(i['name'] == name for i in data['ingredients']):
            if 'ingredients' not in data:
                data['ingredients'] = []
            data['ingredients'].append({
                'name': name,
                'unit': unit,
                'quantity': '',
                'cost_per_unit': '0.00'
            })

        save_data(data)
        return redirect(request.form.get('next') or '/recipes/add')
    next_url = request.args.get('next', '/recipes/add')
    return render_template('ingredient_quickadd.html', ingredient=None, next=next_url)

@ingredients_bp.route('/ingredients/zero/<int:index>', methods=["POST"])
def zero_ingredient(index):
    data = load_data()
    ingredients = data.get("ingredients", [])
    undo_stack = data.setdefault("undo_stack", [])

    if index >= len(ingredients):
        return "Ingredient not found", 404

    ing = ingredients[index]
    previous_qty = ing.get("quantity", 0)
    ing["quantity"] = 0

    undo_stack.append({
        "index": index,
        "previous_quantity": previous_qty,
        "timestamp": datetime.now().isoformat()
    })

    save_data(data)
    return redirect("/ingredients")

@ingredients_bp.route('/ingredients/undo', methods=["POST"])
def undo_last_ingredient_change():
    data = load_data()
    ingredients = data.get("ingredients", [])
    undo_stack = data.setdefault("undo_stack", [])

    if not undo_stack:
        return "Nothing to undo", 400

    last = undo_stack.pop()
    index = last["index"]

    if index < len(ingredients):
        ingredients[index]["quantity"] = last["previous_quantity"]

    save_data(data)
    return redirect("/ingredients")