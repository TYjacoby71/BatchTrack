
from flask import Blueprint, request, jsonify
from services.stock_check_service import check_stock

stock_check_api_bp = Blueprint('stock_check_api', __name__)

@stock_check_api_bp.route('/api/check-stock', methods=['POST'])
def api_check_stock():
    data = request.get_json()

    recipe_id = data.get('recipe_id')
    scale = float(data.get('scale', 1.0))
    flex_mode = data.get('flex_mode', False)
    containers = data.get('containers', [])

    if not recipe_id:
        return jsonify({'error': 'Missing recipe_id'}), 400

    stock_check_result = check_stock(recipe_id, scale, containers, flex_mode)
    return jsonify(stock_check_result), 200
