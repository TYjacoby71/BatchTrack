
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data
from datetime import datetime

update_stock_bp = Blueprint('update_stock', __name__)

@update_stock_bp.route('/inventory/update', methods=['GET', 'POST'])
def update_stock():
    data = load_data()
    ingredients = data.get("ingredients", [])

    if request.method == "POST":
        names = request.form.getlist('ingredient_name[]')
        deltas = request.form.getlist('delta[]')
        units = request.form.getlist('unit[]')
        reasons = request.form.getlist('reason[]')
        
        for name, delta_str, unit, reason in zip(names, deltas, units, reasons):
            ing = next((i for i in ingredients if i["name"].lower() == name.lower()), None)
            if not ing:
                continue
                
            try:
                if not delta_str.strip():
                    continue
                    
                delta = float(delta_str)
                
                if reason in ["Loss", "Spoiled", "Donation"]:
                    delta = -abs(delta)
                else:
                    delta = abs(delta)

                # Convert delta to ingredient's unit if different
                from unit_converter import UnitConversionService
converter = UnitConversionService()
                input_unit = unit
                stored_unit = ing.get("unit")
                
                if input_unit != stored_unit:
                    converted_delta = convert_units(delta, input_unit, stored_unit)
                    if converted_delta is None:
                        continue  # Skip if units are incompatible
                    delta = converted_delta
                
                current_qty = float(ing.get("quantity", 0))
                new_qty = current_qty + delta
                
                if new_qty < 0:
                    continue
                    
                ing["quantity"] = new_qty

                # Log the change
                data.setdefault("inventory_log", []).append({
                    "name": name,
                    "change": delta,
                    "unit": ing["unit"],
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                })
            except (ValueError, TypeError):
                continue

        data["ingredients"] = ingredients
        save_data(data)
        return redirect("/ingredients")

    return render_template("update_stock.html", ingredients=ingredients)
