
from flask import Blueprint, render_template, request, redirect, jsonify
from app.routes.utils import load_data, save_data
from unit_converter import check_stock_availability

batch_flow_bp = Blueprint('batch_flow', __name__)

@batch_flow_bp.route('/api/recipes/list', methods=['GET'])
def get_recipes():
    data = load_data()
    return jsonify({"recipes": data.get("recipes", [])})

@batch_flow_bp.route('/api/stock/check/<int:recipe_id>', methods=['GET'])
def check_recipe_stock(recipe_id):
    data = load_data()
    recipe = next((r for r in data['recipes'] if r['id'] == recipe_id), None)
    if not recipe:
        return jsonify({"error": "Recipe not found"}), 404
        
    stock_status = []
    has_low_stock = False
    inventory = data.get("ingredients", [])
    
    for item in recipe.get("ingredients", []):
        match = next((i for i in inventory if i["name"].lower() == item["name"].lower()), None)
        if not match:
            has_low_stock = True
            stock_status.append({
                "ingredient": item["name"],
                "status": "LOW",
                "needed": float(item["quantity"]),
                "available": 0,
                "unit": item.get("unit", "units")
            })
            continue
            
        try:
            check = check_stock_availability(
                float(item["quantity"]), 
                item.get("unit", "units"),
                float(match["quantity"]), 
                match.get("unit", "units"),
                material=item["name"].lower()
            )
            if check["status"] == "LOW":
                has_low_stock = True
            stock_status.append({
                "ingredient": item["name"],
                "status": check["status"],
                "needed": float(item["quantity"]),
                "available": check["converted"],
                "unit": item.get("unit", "units")
            })
        except (ValueError, TypeError):
            has_low_stock = True
            stock_status.append({
                "ingredient": item["name"],
                "status": "ERROR",
                "needed": float(item["quantity"]),
                "available": 0,
                "unit": item.get("unit", "units")
            })
            
    return jsonify({
        "has_low_stock": has_low_stock,
        "stock_status": stock_status
    })
