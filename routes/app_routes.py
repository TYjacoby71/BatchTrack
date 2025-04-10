
from flask import Blueprint, render_template, request, redirect, url_for, session
from models import Recipe, Ingredient, Batch
from stock_check_utils import check_stock_for_recipe
from flask_login import login_required, current_user

app_routes_bp = Blueprint('home', __name__)

@app_routes_bp.route("/", methods=["GET", "POST"])
@login_required
def homepage():
    recipes = Recipe.query.all()
    active_batch = Batch.query.filter(Batch.total_cost == None).first()
    stock_check = None
    selected_recipe = None
    scale = 1
    status = None

    if request.method == "POST":
        recipe_id = request.form.get("recipe_id")
        scale = float(request.form.get("scale", 1))
        selected_recipe = Recipe.query.get(recipe_id)
        if selected_recipe:
            stock_check = check_stock_for_recipe(selected_recipe, scale)[0]
            status = "ok"
            for item in stock_check:
                if item["status"] == "NEEDED":
                    status = "bad"
                    break
                elif item["status"] == "LOW":
                    status = "low"

    return render_template("homepage.html", 
                         recipes=recipes,
                         stock_check=stock_check,
                         selected_recipe=selected_recipe,
                         scale=scale,
                         status=status,
                         active_batch=active_batch,
                         current_user=current_user)
