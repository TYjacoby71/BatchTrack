
from flask import Blueprint, render_template, request, redirect, jsonify
from app.routes.utils import load_data, save_data
from unit_converter import convert_units

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/recipes', methods=['GET'])
def list_recipes():
    data = load_data()
    return render_template('recipe_list.html', recipes=data['recipes'])

@recipes_bp.route('/check-stock/<int:recipe_id>', methods=['GET'])
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

        if item.get('unit') and ing.get('unit') and item['unit'] != ing['unit']:
            converted_qty = convert_units(needed_qty, item['unit'], ing['unit'])
            if converted_qty is not None:
                needed_qty = converted_qty

        if available_qty < needed_qty:
            stock_check.append({"ingredient": item['name'], "status": "Insufficient"})
        else:
            stock_check.append({"ingredient": item['name'], "status": "OK"})

    return jsonify({"stock_check": stock_check})
