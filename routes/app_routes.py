from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from models import Recipe, InventoryItem, Batch
from services.stock_check import universal_stock_check
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

@app_routes_bp.route('/stock/check', methods=['POST'])
@login_required
def check_stock():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        recipe_id = data.get('recipe_id')
        if not recipe_id:
            return jsonify({"error": "Recipe ID is required"}), 400

        try:
            scale = float(data.get('scale', 1.0))
            if scale <= 0:
                return jsonify({"error": "Scale must be greater than 0"}), 400
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid scale value"}), 400

        recipe = Recipe.query.get_or_404(recipe_id)
        
        # Use universal stock check service
        result = universal_stock_check(recipe, scale)
        stock_check = result['stock_check']
        all_ok = result['all_ok']
        
        # Handle container validation
        container_ids = data.get('container_ids', [])
        if container_ids and isinstance(container_ids, list):
            container_check, containers_ok = check_container_availability(container_ids, scale)
            stock_check.extend(container_check)
            all_ok = all_ok and containers_ok

        status = "ok" if all_ok else "bad"
        for item in stock_check:
            if item["status"] == "LOW" and status != "bad":
                status = "low"
                break

        # Format the response to match template expectations
        results = [{
            'name': item['name'],
            'needed': item['needed'],
            'available': item['available'],
            'unit': item['unit'],
            'status': item['status'],
            'type': item.get('type', 'ingredient')
        } for item in stock_check]
        
        return jsonify({
            "stock_check": results,
            "status": status,
            "all_ok": all_ok,
            "recipe_name": recipe.name
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required

app_bp = Blueprint('app', __name__)

@app_bp.route('/unit-manager')
@login_required
def unit_manager():
    return redirect(url_for('conversion.manage_units'))