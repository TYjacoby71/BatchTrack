
from flask import Blueprint, request, render_template, redirect, flash
from app.routes.utils import load_data, save_data
from datetime import datetime

adjust_bp = Blueprint("adjust", __name__)

@adjust_bp.route('/inventory/adjust', methods=['GET', 'POST'])
def adjust_inventory():
    data = load_data()
    inventory = data.get("ingredients", [])
    reasons = ["Purchase", "Donation", "Spoiled", "Sample", "Test Batch", "Error", "Sync", "Other"]

    if request.method == 'POST':
        for i in inventory:
            name = i["name"]
            unit = i["unit"]
            qty_delta = request.form.get(f"adj_{name}", "0")
            reason = request.form.get(f"reason_{name}")

            try:
                delta = float(qty_delta or 0)
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
                    new_qty = float(i["quantity"] or 0) + delta
                    if new_qty < 0:
                        flash("Error: Quantity cannot be negative")
                        return redirect('/inventory/adjust')
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
