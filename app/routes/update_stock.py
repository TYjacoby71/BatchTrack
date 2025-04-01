
from flask import Blueprint, render_template, request, redirect
from app.routes.utils import load_data, save_data
from datetime import datetime

update_stock_bp = Blueprint('update_stock', __name__)

@update_stock_bp.route('/inventory/update', methods=['GET', 'POST'])
def update_stock():
    data = load_data()
    ingredients = data.get("ingredients", [])
    reasons = ["Purchase", "Donation", "Spoiled", "Sample", "Test Batch", "Error", "Sync", "Other"]

    if request.method == "POST":
        to_update = request.form.getlist("update")

        for name in to_update:
            ing = next((i for i in ingredients if i["name"].lower() == name.lower()), None)
            if not ing:
                continue
            delta_key = f"delta_{name}"
            reason_key = f"reason_{name}"
            try:
                delta = float(request.form.get(delta_key, 0))
                reason = request.form.get(reason_key, "Unspecified")
                current_qty = float(ing.get("quantity", 0))
                ing["quantity"] = current_qty + delta

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

    return render_template("update_stock.html", ingredients=ingredients, reasons=reasons)
