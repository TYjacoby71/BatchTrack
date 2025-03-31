from flask import Blueprint, render_template, request, redirect
from app.routes.utils import load_data, save_data
import json

ingredients_bp = Blueprint('ingredients', __name__)

@ingredients_bp.route('/')
def index():
    data = load_data()
    ingredients = data.get('ingredients', [])

    low_stock = []
    for ing in ingredients:
        print(f"Checking ingredient: {ing['name']} → quantity: {ing['quantity']}")
        try:
            qty = float(ing.get("quantity", 0))
            if qty < 10:
                print(f"⚠️ Low stock: {ing['name']} at {qty}")
                low_stock.append(ing)
        except Exception as e:
            print(f"Error parsing quantity for {ing.get('name', '?')}: {e}")

    print(f"Found {len(low_stock)} low stock ingredients.")

    recent_batches = sorted(
        data.get("batches", []),
        key=lambda b: b.get("timestamp", ""),
        reverse=True
    )[:5]

    return render_template('dashboard.html', low_stock=low_stock, recent_batches=recent_batches)

@ingredients_bp.route('/ingredients')
def ingredients():
    data = load_data()
    return render_template('ingredients.html', ingredients=data['ingredients'])

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
        return redirect('/ingredients')
    return render_template('edit_ingredient.html', ingredient=None)

@ingredients_bp.route('/edit-ingredient/<name>', methods=['GET', 'POST'])
def edit_ingredient(name):
    data = load_data()
    ingredient = next((i for i in data['ingredients'] if i['name'] == name), None)
    if not ingredient:
        return "Ingredient not found", 404

    if request.method == 'POST':
        new_name = request.form['name']
        # Update name in ingredient list
        ingredient['name'] = new_name
        ingredient['quantity'] = request.form['quantity']
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

    with open('units.json', 'r') as f:
        units = json.load(f)
    return render_template('add_ingredient.html', units=units)