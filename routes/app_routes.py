
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from models import Recipe, InventoryItem, Batch
from stock_check_utils import check_stock_for_recipe
from flask_login import login_required, current_user

app_routes_bp = Blueprint('home', __name__)

@app_routes_bp.route("/", methods=["GET", "POST"])
@login_required
def homepage():
    recipes = Recipe.query.all()
    active_batch = Batch.query.filter_by(status='in_progress').order_by(Batch.timestamp.desc()).first()
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

    return render_template("homepage.html", 
                         recipes=recipes,
                         stock_check=stock_check,
                         selected_recipe=selected_recipe,
                         scale=scale,
                         status=status,
                         active_batch=active_batch,
                         current_user=current_user)

@app_routes_bp.route('/stock/check', methods=['POST'])
@login_required
def check_stock():
    data = request.json
    recipe_id = data.get('recipe_id')
    scale = float(data.get('scale', 1.0))

    if not recipe_id or scale <= 0:
        return jsonify({"error": "Invalid input"}), 400

    recipe = Recipe.query.get_or_404(recipe_id)
    stock_check, all_ok = check_stock_for_recipe(recipe, scale)
    status = "ok" if all_ok else "bad"
    for item in stock_check:
        if item["status"] == "LOW" and status != "bad":
            status = "low"
            break

    return jsonify({
        "stock_check": stock_check,
        "status": status,
        "all_ok": all_ok,
        "recipe_name": recipe.name
    }), 200
