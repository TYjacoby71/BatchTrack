from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from app.services.stock_check import UniversalStockCheckService
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

        print(f"Found recipe: {recipe.name} with {len(recipe.recipe_ingredients)} ingredients")

        # Debug recipe ingredients
        for ri in recipe.recipe_ingredients:
            ingredient = ri.inventory_item
            print(f"Recipe ingredient: {ri.quantity} {ri.unit} of {ingredient.name if ingredient else 'MISSING'}")
            if ingredient:
                print(f"  - Ingredient org_id: {ingredient.organization_id}, current qty: {ingredient.quantity} {ingredient.unit}")
            else:
                print(f"  - WARNING: Ingredient is None for recipe ingredient ID {ri.id}")

        # Use new Universal Stock Check Service
        service = UniversalStockCheckService()
        result = service.check_recipe_stock(recipe, scale)
        print(f"Stock check result: {result}")

        # Format response for frontend compatibility
        stock_results = []
        for item in result['stock_check']:
            stock_results.append({
                'name': item['name'],
                'needed': item['needed'],
                'available': item['available'],
                'unit': item['needed_unit'],
                'status': item['status'],
                'type': item.get('type', 'ingredient')
            })

        return jsonify({
            "stock_check": stock_results,
            "all_ok": result['all_ok'],
            "status": "ok" if result['all_ok'] else "bad"
        })

    except Exception as e:
        print(f"Stock check API error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400