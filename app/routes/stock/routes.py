
from flask import Blueprint, render_template, request, redirect, Response, jsonify, flash, session
from app.routes.utils import load_data, save_data
from unit_converter import UnitConversionService, check_stock_availability, can_fulfill
from datetime import datetime
import json

stock_bp = Blueprint('stock', __name__)
converter = UnitConversionService()

def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def check_stock_for_recipes(recipe_ids=None, batch_counts=None):
    """Unified stock checking service"""
    data = load_data()
    inventory = data.get("ingredients", [])
    recipes = data.get("recipes", [])

    # Initialize tracking
    usage = {}
    stock_report = []
    needed_items = {}

    # Handle single recipe case
    if isinstance(recipe_ids, int):
        recipe_ids = [recipe_ids]
        batch_counts = [1.0]

    # If no recipes specified, check all inventory
    if not recipe_ids:
        for ingredient in inventory:
            name = ingredient["name"]
            qty = safe_float(ingredient.get("quantity", 0))
            unit = ingredient.get("unit", "units")

            status = "OK" if qty > 10 else "LOW"  # Simple threshold check
            stock_report.append({
                "name": name,
                "needed": "0",
                "available": f"{qty} {unit}",
                "status": status
            })
            if status == "LOW":
                needed_items[name] = {"total": 10 - qty, "unit": unit}
        return stock_report, needed_items

    # Calculate total requirements
    for r_id, count in zip(recipe_ids, batch_counts):
        count = safe_float(count or 0)
        if count > 0:
            recipe = next((r for r in recipes if r["id"] == int(r_id)), None)
            if recipe:
                for item in recipe['ingredients']:
                    base_qty = safe_float(item['quantity'])
                    total_qty = base_qty * count
                    name = item['name']
                    if name not in usage:
                        usage[name] = {
                            'qty': total_qty,
                            'unit': item.get('unit', 'units')
                        }
                    else:
                        usage[name]['qty'] += total_qty

    # Check availability
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

            if check['status'] == "LOW":
                needed_items[name] = {
                    "total": max(0, needed_qty - available_qty),
                    "unit": details['unit']
                }

            stock_report.append({
                "name": name,
                "needed": f"{round(needed_qty, 2)} {details['unit']}",
                "available": f"{available_qty} {check['unit']}",
                "status": check["status"]
            })

        except (ValueError, TypeError):
            stock_report.append({
                "name": name,
                "needed": f"{details['qty']} {details['unit']}",
                "available": "0",
                "status": "LOW"
            })
            needed_items[name] = {
                "total": details['qty'],
                "unit": details['unit']
            }

    return stock_report, needed_items

@stock_bp.route('/check/<int:recipe_id>')
def check_stock_for_recipe(recipe_id):
    data = load_data()
    recipe = next((r for r in data.get("recipes", []) if r["id"] == recipe_id), None)
    if not recipe:
        return "Recipe not found", 404

    stock_report, needed_items = check_stock_for_recipes([recipe_id], [1.0])
    if needed_items:
        session['needed_items'] = needed_items

    return render_template("bulk_stock_results.html", recipe=recipe, stock_report=stock_report, missing_summary=needed_items)

@stock_bp.route('/check-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()
    if request.method == 'POST':
        recipe_ids = [int(id) for id in request.form.getlist('recipe_id')]
        batch_counts = [float(count or 1) for count in request.form.getlist('batch_count')]

        stock_report, needed_items = check_stock_for_recipes(recipe_ids, batch_counts)
        return render_template('bulk_stock_results.html', 
                             stock_report=stock_report, 
                             missing_summary=needed_items)

    return render_template('bulk_stock_check.html', recipes=data.get('recipes', []))

@stock_bp.route('/inventory/check')
def check_all_stock():
    stock_report, needed_items = check_stock_for_recipes()
    return render_template('bulk_stock_results.html', 
                         stock_report=stock_report, 
                         missing_summary=needed_items)

@stock_bp.route('/check-bulk', methods=['GET', 'POST'])
def check_stock_bulk():
    data = load_data()
    if request.method == 'POST':
        recipe_ids = [int(id) for id in request.form.getlist('recipe_id')]
        batch_counts = [float(count or 1) for count in request.form.getlist('batch_count')]

        stock_report, needed_items = check_stock_for_recipes(recipe_ids, batch_counts)
        return render_template('bulk_stock_results.html',
                             stock_report=stock_report,
                             missing_summary=needed_items)

    return render_template('bulk_stock_check.html', recipes=data.get('recipes', []))

@stock_bp.route('/inventory/update', methods=['GET', 'POST'])
def update_stock():
    data = load_data()
    inventory = data.get("ingredients", [])
    reasons = ["Purchase", "Donation", "Spoiled", "Sample", "Test Batch", "Error", "Sync", "Other"]

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
                        if unit != ingredient['unit']:
                            converted_delta = converter.convert(delta, unit, ingredient['unit'])
                            if converted_delta is not None:
                                delta = converted_delta
                            else:
                                continue

                        if reason in ['Loss', 'Spoiled', 'Donation']:
                            delta = -abs(delta)
                        else:
                            delta = abs(delta)

                        current_qty = float(ingredient.get('quantity', 0))
                        ingredient['quantity'] = current_qty + delta

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
        previous_page = request.form.get('referrer') or request.referrer or '/ingredients'
        return redirect(previous_page)

    with open('units.json') as f:
        units = json.load(f)

    return render_template('update_stock.html', 
                         ingredients=data.get('ingredients', []),
                         units=units)

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
