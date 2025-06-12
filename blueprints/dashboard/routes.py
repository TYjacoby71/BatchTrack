
from flask import render_template, request, jsonify
from flask_login import login_required
from models import Recipe, Batch, InventoryItem, db
from . import dashboard_bp

@dashboard_bp.route('/user_dashboard')
@login_required
def dashboard():
    """Main dashboard view"""
    recipes = Recipe.query.filter_by(is_locked=False).all()
    active_batches = Batch.query.filter_by(status='active').all()
    return render_template('dashboard.html', recipes=recipes, active_batches=active_batches)

@dashboard_bp.route('/api/recipes')
@login_required
def api_recipes():
    """API endpoint for recipe data"""
    recipes = Recipe.query.filter_by(is_locked=False).all()
    return jsonify([{
        'id': r.id,
        'name': r.name,
        'label_prefix': r.label_prefix,
        'predicted_yield': r.predicted_yield,
        'predicted_yield_unit': r.predicted_yield_unit
    } for r in recipes])
