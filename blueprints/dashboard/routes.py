
from flask import Blueprint, render_template, request, flash
from flask_login import login_required, current_user
from models import Recipe, Batch
from services.dashboard_alerts import DashboardAlertService
from services.stock_check import check_stock_for_recipe
from utils.permissions import require_permission

dashboard_bp = Blueprint('user_dashboard', __name__, url_prefix='/dashboard')

@dashboard_bp.route('/')
@login_required
@require_permission('dashboard.view')
def dashboard():
    recipes = Recipe.query.all()
    active_batch = Batch.query.filter_by(status='in_progress').first()

    # Get unified dashboard alerts
    alert_data = DashboardAlertService.get_dashboard_alerts()

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
                         alert_data=alert_data)
