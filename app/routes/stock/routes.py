
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

@stock_bp.route('/stock/check-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()
    inventory = data.get("ingredients", [])
    recipes = data.get("recipes", [])

    if request.method == 'POST':
        recipe_ids = request.form.getlist('recipe_id')
        batch_counts = request.form.getlist('batch_count')
        usage = {}

        for r_id, count in zip(recipe_ids, batch_counts):
            count = float(count or 0)
            if count > 0:
                recipe = next((r for r in data['recipes'] if r['id'] == int(r_id)), None)
                if recipe:
                    for item in recipe['ingredients']:
                        base_qty = float(item['quantity'])
                        total_qty = base_qty * count
                        if item['name'] not in usage:
                            usage[item['name']] = {
                                'qty': total_qty,
                                'unit': item.get('unit', 'units')
                            }
                        else:
                            usage[item['name']]['qty'] += total_qty

        stock_report = []
        from app.unit_conversion import check_stock_availability

        for name, details in usage.items():
            current = next((i for i in data['ingredients'] if i['name'].lower() == name.lower()), None)
            try:
                if not current or not current.get('quantity'):
                    raise ValueError("No stock found")

                check = check_stock_availability(
                    details['qty'],
                    details['unit'],
                    current['quantity'],
                    current['unit']
                )
                
                stock_report.append({
                    "name": name,
                    "needed": f"{round(details['qty'], 2)} {details['unit']}",
                    "available": f"{check['converted']} {check['unit']}",
                    "status": check['status']
                })
            except (ValueError, TypeError):
                stock_report.append({
                    "name": name,
                    "needed": details['qty'],
                    "available": 0,
                    "unit": details['unit'],
                    "status": "LOW"
                })

        return render_template('bulk_stock_results.html', stock_report=stock_report)

    return render_template('bulk_stock_check.html', recipes=data['recipes'])
