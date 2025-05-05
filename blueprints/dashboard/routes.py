
from flask import Blueprint, render_template, request
from models import Recipe, Batch
from services.inventory_alerts import get_low_stock_ingredients
from services.expiration_alerts import get_expired_inventory

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates')

@dashboard_bp.route("/")
def dashboard():
    recipes = Recipe.query.all()
    active_batch = Batch.query.filter_by(status='in_progress').first()
    low_stock_items = get_low_stock_ingredients()
    expired = get_expired_inventory()
    
    return render_template("dashboard.html", 
                         recipes=recipes,
                         active_batch=active_batch,
                         low_stock_items=low_stock_items,
                         expired=expired)
