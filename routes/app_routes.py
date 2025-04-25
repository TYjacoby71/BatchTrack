from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from models import Recipe, InventoryItem, Batch
from stock_check_utils import check_stock_for_recipe
from flask_login import login_required, current_user

app_routes_bp = Blueprint('dashboard', __name__)

from services.inventory_alerts import get_low_stock_ingredients
from services.expiration_alerts import get_expired_inventory

@app_routes_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    recipes = Recipe.query.all()
    active_batch = Batch.query.filter_by(status='in_progress').first()
    low_stock_items = get_low_stock_ingredients()
    expired = get_expired_inventory()
    stock_check = None
    selected_recipe = None
    scale = 1
    status = None

    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        try:
            scale = float(request.form.get("scale", 1))
            selected_recipe = Recipe.query.get(recipe_id)
            if selected_recipe:
                stock_check, all_ok = check_stock_for_recipe(selected_recipe, scale)
                status = "ok" if all_ok else "bad"
                for item in stock_check:
                    if item["status"] == "LOW" and status != "bad":
                        status = "low"
                        break
        except ValueError as e:
            flash("Invalid scale value")

    return render_template("dashboard.html", 
                         recipes=recipes,
                         stock_check=stock_check,
                         selected_recipe=selected_recipe,
                         scale=scale,
                         status=status,
                         active_batch=active_batch,
                         current_user=current_user,
                         low_stock_items=low_stock_items,
                         expired=expired)

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

app_bp = Blueprint('app', __name__)

@app_bp.route('/unit-manager')
@login_required
def unit_manager():
    return redirect(url_for('conversion.manage_units'))