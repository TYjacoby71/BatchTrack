from flask import Blueprint, render_template, request, redirect, flash, url_for
from app.routes.utils import load_data, save_data
from app.unit_conversion import check_stock_availability, can_fulfill
from datetime import datetime
import json

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

    return render_template("single_recipe_stock.html", recipe=recipe, stock_check=stock_check)

@stock_bp.route('/update', methods=['GET', 'POST'])
def update_inventory():
    data = load_data()
    ingredients = data.get("ingredients", [])

    if request.method == 'POST':
        for ing in ingredients:
            name = ing['name']
            new_qty = request.form.get(f'quantity_{name}')
            if new_qty is not None:
                try:
                    new_qty = float(new_qty)
                    ing['quantity'] = round(new_qty, 2)

                    # Log the change
                    data.setdefault("inventory_log", []).append({
                        "name": name,
                        "change": new_qty,
                        "unit": ing.get('unit', 'units'),
                        "reason": "Update",
                        "timestamp": datetime.now().isoformat()
                    })
                except (ValueError, TypeError):
                    continue

        data['ingredients'] = ingredients
        save_data(data)
        return redirect('/ingredients')

    with open('units.json') as f:
        units = json.load(f)

    return render_template("update_stock.html", ingredients=ingredients, units=units)

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
                if not current:
                    raise ValueError("No stock found")
                current_qty = float(current.get('quantity', 0))

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