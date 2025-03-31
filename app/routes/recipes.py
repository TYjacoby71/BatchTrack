from flask import Blueprint, render_template, jsonify, request
from app.routes.utils import load_data

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/recipes')
def recipes():
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