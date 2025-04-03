from flask import Blueprint, render_template, request, redirect, Response, jsonify, flash
from app.routes.utils import load_data, save_data
from unit_converter import UnitConversionService, check_stock_availability, can_fulfill

converter = UnitConversionService()
from datetime import datetime
import json

from . import stock_bp

def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


@stock_bp.route('/check/<int:recipe_id>')
def check_stock_for_recipe(recipe_id):
    data = load_data()
    inventory = data.get("ingredients", [])
    recipe = next((r for r in data.get("recipes", []) if r["id"] == recipe_id), None)

    if not recipe:
        return "Recipe not found", 404

    stock_check = []
    for item in recipe.get("ingredients", []):
        name = item["name"]
        qty = safe_float(item["quantity"]) # Use safe_float here
        unit = item.get("unit", "units")

        match = next((i for i in inventory if i["name"].lower() == name.lower()), None)

        if match:
            # Pass material type for proper density conversion
            try:
                check = check_stock_availability(
                    qty, unit,
                    safe_float(match["quantity"]), match["unit"], # Use safe_float here
                    material=name.lower()
                )
            except (ValueError, TypeError) as e:
                check = {"converted": 0, "unit": unit, "status": "ERROR"}
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



@stock_bp.route('/check-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()
    inventory = data.get("ingredients", [])
    recipes = data.get("recipes", [])

    if request.method == 'POST':
        recipe_ids = request.form.getlist('recipe_id')
        batch_counts = request.form.getlist('batch_count')
        usage = {}

        for r_id, count in zip(recipe_ids, batch_counts):
            count = safe_float(count or 0)
            if count > 0:
                recipe = next((r for r in data['recipes'] if r['id'] == int(r_id)), None)
                if recipe:
                    for item in recipe['ingredients']:
                        base_qty = safe_float(item['quantity'])
                        total_qty = base_qty * count
                        if item['name'] not in usage:
                            usage[item['name']] = {
                                'qty': total_qty,
                                'unit': item.get('unit', 'units')
                            }
                        else:
                            usage[item['name']]['qty'] += total_qty

        stock_report = []
        needed_items = {}

        for name, details in usage.items():
            current = next((i for i in inventory if i['name'].lower() == name.lower()), None)
            try:
                if not current or not current.get('quantity'):
                    raise ValueError("No stock found")

                check = check_stock_availability(
                    safe_float(details['qty']),
                    details['unit'],
                    safe_float(current['quantity']),
                    current['unit'],
                    material=name.lower()
                )

                stock_report.append({
                    "name": name,
                    "needed": f"{round(details['qty'], 2)} {details['unit']}",
                    "available": f"{check['converted']} {check['unit']}",
                    "status": check['status']
                })

                if check['status'] == "LOW":
                    if name not in needed_items:
                        needed_items[name] = {"total": 0, "unit": details['unit']}
            except (ValueError, TypeError):
                stock_report.append({
                    "name": name,
                    "needed": details['qty'],
                    "available": 0,
                    "unit": details['unit'],
                    "status": "LOW"
                })

        return render_template('bulk_stock_results.html', stock_report=stock_report, missing_summary=needed_items)

    return render_template('bulk_stock_check.html', recipes=recipes)

@stock_bp.route('/inventory/adjust', methods=['GET', 'POST'])
def adjust_inventory():
    data = load_data()
    ingredients = data.get("ingredients", [])

    if request.method == 'POST':
        ingredient_names = request.form.getlist('ingredient_name[]')
        deltas = request.form.getlist('delta[]')
        units = request.form.getlist('unit[]')

        for name, delta_str, unit in zip(ingredient_names, deltas, units):
            try:
                if not delta_str:
                    continue

                delta = safe_float(delta_str) # Use safe_float here
                ingredient = next((i for i in ingredients if i['name'] == name), None)

                if ingredient:
                    current_qty = safe_float(ingredient.get('quantity', 0)) # Use safe_float here

                    # Convert units if they don't match
                    if unit != ingredient['unit']:
                        converted_delta = converter.convert(delta, unit, ingredient['unit'], material=name.lower())
                        if converted_delta is not None:
                            delta = converted_delta
                            print(f"Converting {delta} {unit} to {converted_delta} {ingredient['unit']}")
                        else:
                            flash(f"Could not convert {unit} to {ingredient['unit']} - please check units.json for valid conversion")
                            continue

                    ingredient['quantity'] = round(current_qty + delta, 2)
                    print(f"Updated {name} from {current_qty} to {ingredient['quantity']} {ingredient['unit']}")

                    data.setdefault("inventory_log", []).append({
                        "name": name,
                        "change": delta,
                        "unit": ingredient['unit'],
                        "reason": "Stock Update",
                        "timestamp": datetime.now().isoformat()
                    })

            except (ValueError, TypeError) as e:
                flash(f"Error updating {name}: {str(e)}")
                continue

        save_data(data)
        return redirect('/ingredients')

    with open('units.json') as f:
        units = json.load(f)

    return render_template("update_stock.html", ingredients=ingredients, units=units)

@stock_bp.route('/stock/inventory/adjust', methods=['GET', 'POST'])
def adjust_inventory():
    data = load_data()
    inventory = data.get("ingredients", [])
    reasons = ["Purchase", "Donation", "Spoiled", "Sample", "Test Batch", "Error", "Sync", "Other"]

    if request.method == 'POST':
        for i in inventory:
            name = i["name"]
            unit = i["unit"]
            qty_delta = request.form.get(f"adj_{name}")
            reason = request.form.get(f"reason_{name}")

            if qty_delta:
                try:
                    delta = safe_float(qty_delta) # Use safe_float here
                    input_unit = request.form.get(f"unit_{name}", unit)

                    if input_unit != unit:
                        from unit_converter import UnitConversionService
                        converter = UnitConversionService()
                        converted_delta = converter.convert(delta, input_unit, unit)
                        if converted_delta is not None:
                            delta = converted_delta
                        else:
                            continue

                    if "quantity" in i:
                        new_qty = safe_float(i["quantity"] or 0) + delta # Use safe_float here
                        if new_qty < 0:
                            flash("Error: Quantity cannot be negative")
                            return redirect('/stock/inventory/adjust')
                        i["quantity"] = new_qty
                    else:
                        i["quantity"] = delta

                    data.setdefault("inventory_log", []).append({
                        "name": name,
                        "change": delta,
                        "unit": unit,
                        "reason": reason or "Unspecified",
                        "timestamp": datetime.now().isoformat()
                    })

                except ValueError:
                    continue

        data["ingredients"] = inventory
        save_data(data)
        return redirect("/ingredients")

    return render_template("inventory_adjust.html", ingredients=inventory, reasons=reasons)