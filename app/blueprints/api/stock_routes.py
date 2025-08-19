from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...services.stock_check.core import UniversalStockCheckService
from ...models import Recipe

stock_api_bp = Blueprint('stock_api', __name__)

@stock_api_bp.route('/check-stock', methods=['POST'])
@login_required
def check_stock():
    try:
        data = request.get_json()
        recipe_id = data.get('recipe_id')
        scale = float(data.get('scale', 1.0))

        print(f"Stock check request - recipe_id: {recipe_id}, scale: {scale}, user org: {current_user.organization_id}")

        # Use scoped query to ensure recipe belongs to current user's organization
        recipe = Recipe.scoped().filter_by(id=recipe_id).first()
        if not recipe:
            print(f"Recipe {recipe_id} not found for organization {current_user.organization_id}")
            return jsonify({"error": "Recipe not found"}), 404

        print(f"Found recipe: {recipe.name} with {len(recipe.ingredients)} ingredients")

        # Use new UniversalStockCheckService
        service = UniversalStockCheckService()
        result = service.check_recipe_stock(recipe, scale)
        print(f"Stock check result: {result}")

        return jsonify(result)

    except Exception as e:
        print(f"Stock check API error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400