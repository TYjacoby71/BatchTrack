from flask import Blueprint, render_template, request, redirect
from app.routes.utils import load_data, save_data
import json

ingredients_bp = Blueprint('ingredients', __name__)

@ingredients_bp.route('/')
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

@ingredients_bp.route('/add-ingredient', methods=['GET', 'POST'])
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