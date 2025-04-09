
from flask import Blueprint, render_template, request
from flask_login import login_required
from models import db, Recipe
from stock_check_utils import check_stock_for_recipe

recipes_bp = Blueprint('recipes', __name__)

@recipes_bp.route('/recipes/<int:recipe_id>/plan', methods=['GET', 'POST'])
@login_required
def plan_production(recipe_id):
    recipe = Recipe.query.get_or_404(recipe_id)
    scale = float(request.form.get('scale', 1.0)) if request.method == 'POST' else 1.0
    stock_check, all_ok = check_stock_for_recipe(recipe, scale)

    return render_template('plan_production.html', recipe=recipe, scale=scale,
                           stock_check=stock_check, all_ok=all_ok)
