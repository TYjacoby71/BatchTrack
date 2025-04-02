
from flask import Blueprint, render_template, request, redirect, Response, jsonify
from app.routes.utils import load_data, save_data
from app.unit_conversion import check_stock_availability, can_fulfill
from datetime import datetime

from . import stock_bp

@stock_bp.route('/stock/check/<int:recipe_id>')
def check_stock_for_recipe(recipe_id):
    data = load_data()
    inventory = data.get("ingredients", [])
    recipe = next((r for r in data.get("recipes", []) if r["id"] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    stock_check = []
    for item in recipe.get("ingredients", []):
        name = item["name"]
        qty = float(item["quantity"])
        unit = item.get("unit", "units")

        match = next((i for i in inventory if i["name"].lower() == name.lower()), None)

        if match:
            check = check_stock_availability(
                qty, unit,
                match["quantity"], match["unit"]
            )
            stock_check.append({
                "name": name,
                "needed": f"{qty} {unit}",
                "available": f"{check['converted']} {check['unit']}",
                "status": check["status"]
            })
        else:
            stock_check.append({
                "name": name,
                "needed": f"{qty} {unit}",
                "available": f"0 {unit}",
                "status": "LOW"
            })

    return render_template("stock_status.html", recipe=recipe, stock_check=stock_check)
