from flask import Blueprint, request, jsonify
from models import db, Recipe
from services.stock_check import universal_stock_check
import logging

logger = logging.getLogger(__name__)
stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/api/check-stock', methods=['POST'])
def api_check_stock():
    data = request.get_json()
    recipe_id = data.get('recipe_id')
    scale = float(data.get('scale', 1))
    flex_mode = data.get('flex_mode', False)

    recipe = Recipe.query.get(recipe_id)
    if not recipe:
        return jsonify({'error': 'Recipe not found'}), 404

    report = []
    all_ok = True

    for ri in recipe.recipe_ingredients:
        required_qty = ri.amount * scale
        stock_qty = ri.inventory_item.quantity
        status = "OK" if stock_qty >= required_qty else "LOW"
        if status != "OK":
            all_ok = False
        report.append({
            "ingredient": ri.inventory_item.name,
            "needed": round(required_qty, 2),
            "available": round(stock_qty, 2),
            "recipe_unit": ri.unit,
            "inventory_unit": ri.inventory_item.unit,
            "status": status
        })

    return jsonify({
        "all_ok": all_ok,
        "ingredients": report
    })