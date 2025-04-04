from flask import Blueprint, render_template, request, redirect, Response, jsonify, flash, session
from app.routes.utils import load_data, save_data
from unit_converter import UnitConversionService, check_stock_availability, can_fulfill

converter = UnitConversionService()
from datetime import datetime
import json

from . import stock_bp

@stock_bp.route('/inventory/update', methods=['GET', 'POST'])
def update_stock():
    data = load_data()

    if request.method == 'POST':
        ingredients = data.get('ingredients', [])
        ingredient_names = request.form.getlist('ingredient_name[]')
        deltas = request.form.getlist('delta[]')
        units = request.form.getlist('unit[]')
        reasons = request.form.getlist('reason[]')

        for name, delta_str, unit, reason in zip(ingredient_names, deltas, units, reasons):
            if delta_str:  # Only process if delta is provided
                try:
                    delta = float(delta_str)
                    ingredient = next((i for i in ingredients if i['name'] == name), None)
                    if ingredient:
                        # Convert units if necessary
                        if unit != ingredient['unit']:
                            from unit_converter import UnitConversionService
                            converter = UnitConversionService()
                            converted_delta = converter.convert(delta, unit, ingredient['unit'])
                            if converted_delta is not None:
                                delta = converted_delta
                            else:
                                continue

                        # Apply the change based on reason
                        if reason in ['Loss', 'Spoiled', 'Donation']:
                            delta = -abs(delta)  # Make sure it's negative for removals
                        else:
                            delta = abs(delta)  # Make sure it's positive for additions

                        current_qty = float(ingredient.get('quantity', 0))
                        ingredient['quantity'] = current_qty + delta

                        # Log the change
                        data.setdefault('inventory_log', []).append({
                            'name': name,
                            'change': delta,
                            'unit': ingredient['unit'],
                            'reason': reason,
                            'timestamp': datetime.now().isoformat()
                        })
                except ValueError:
                    continue

        save_data(data)
        # Get the referrer from form data, fallback to HTTP referrer, then ingredients page
        previous_page = request.form.get('referrer') or request.referrer or '/ingredients'
        return redirect(previous_page)

    # Load units from JSON file
    with open('units.json') as f:
        units = json.load(f)

    return render_template('update_stock.html', 
                         ingredients=data.get('ingredients', []),
                         units=units)

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

    # Clear any existing stock alerts from session
    if 'needed_items' in session:
        del session['needed_items']

    stock_check = []
    needed_items = {}

    for item in recipe.get("ingredients", []):
        name = item["name"]
        qty = safe_float(item["quantity"])
        unit = item.get("unit", "units")

        match = next((i for i in inventory if i["name"].lower() == name.lower()), None)

        if match:
            try:
                check = check_stock_availability(
                    qty, unit,
                    safe_float(match["quantity"]), match["unit"],
                    material=name.lower()
                )
                if check["status"] == "LOW":
                    needed_qty = qty - check["converted"]
                    needed_items[name] = {
                        "total": max(0, needed_qty),
                        "unit": unit
                    }
            except (ValueError, TypeError) as e:
                check = {"converted": 0, "unit": unit, "status": "ERROR"}
                needed_items[name] = {"total": qty, "unit": unit}
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
            needed_items[name] = {"total": qty, "unit": unit}

    if needed_items:
        session['needed_items'] = needed_items

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

                needed_qty = float(details['qty'])
                available_qty = float(check['converted'])

                stock_report.append({
                    "name": name,
                    "needed": f"{round(needed_qty, 2)} {details['unit']}",
                    "available": f"{available_qty} {check['unit']}",
                    "status": check["status"]
                })

                if check['status'] == "LOW":
                    if name not in needed_items:
                        needed_items[name] = {"total": max(0, needed_qty - available_qty), "unit": details['unit']}
                    else:
                        needed_items[name]["total"] += max(0, needed_qty - available_qty)

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
                    delta = safe_float(qty_delta)
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
                        new_qty = safe_float(i["quantity"] or 0) + delta
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