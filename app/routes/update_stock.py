
from flask import Blueprint, render_template, request, redirect, flash
from app.routes.utils import load_data, save_data
from datetime import datetime

update_stock_bp = Blueprint('update_stock', __name__)

@update_stock_bp.route('/inventory/update', methods=['GET', 'POST'])
def update_stock():
    data = load_data()
    ingredients = data.get("ingredients", [])

    if request.method == "POST":
        for ing in ingredients:
            name = ing["name"]
            ing = next((i for i in ingredients if i["name"].lower() == name.lower()), None)
            if not ing:
                continue
                
            delta_key = f"delta_{name}"
            reason_key = f"reason_{name}"
            
            try:
                delta = float(request.form.get(delta_key, 0))
                reason = request.form.get(reason_key, "Unspecified")
                
                # If reason indicates removal, make delta negative
                if reason in ["Loss", "Spoiled", "Used", "Donation"]:
                    delta = -abs(delta)
                else:
                    delta = abs(delta)
                
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
