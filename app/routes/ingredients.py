from flask import Blueprint, render_template, request, redirect
from app.routes.utils import load_data, save_data
import json

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
        referer = request.headers.get('Referer')
        if referer and '/recipes' in referer:
            return redirect(referer)
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