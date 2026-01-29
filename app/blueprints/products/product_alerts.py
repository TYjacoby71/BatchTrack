from flask import render_template, jsonify
from flask_login import login_required
from app.utils.permissions import require_permission
from ...services.combined_inventory_alerts import CombinedInventoryAlertService
from . import products_bp

@products_bp.route('/alerts')
@login_required
@require_permission('alerts.view')
def product_alerts():
    """Product alerts dashboard for low stock and out of stock items"""
    stock_summary = CombinedInventoryAlertService.get_product_stock_summary()

    return render_template('pages/products/alerts.html', 
                         stock_summary=stock_summary)

@products_bp.route('/api/stock-summary')
@login_required
@require_permission('alerts.view')
def api_stock_summary():
    """API endpoint for product stock summary"""
    summary = CombinedInventoryAlertService.get_product_stock_summary()
    return jsonify(summary)