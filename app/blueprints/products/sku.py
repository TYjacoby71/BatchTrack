
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, ProductSKU, ProductSKUHistory
from ...utils.unit_utils import get_global_unit_list

# Create the sku blueprint
sku_bp = Blueprint('sku', __name__)

@sku_bp.route('/sku/<int:sku_id>')
@login_required
def view_sku(sku_id):
    """View individual SKU details"""
    sku = ProductSKU.query.get_or_404(sku_id)

    # Get SKU history for this specific SKU
    history = ProductSKUHistory.query.filter_by(sku_id=sku_id).order_by(ProductSKUHistory.timestamp.desc()).all()

    # Calculate total quantity from current_quantity
    total_quantity = sku.current_quantity or 0

    return render_template('products/view_sku.html',
                         sku=sku,
                         history=history,
                         total_quantity=total_quantity,
                         get_global_unit_list=get_global_unit_list)

@sku_bp.route('/sku/<int:sku_id>/adjust', methods=['POST'])
@login_required
def adjust_sku(sku_id):
    """Legacy route - redirect to consolidated product inventory adjustment"""
    # Redirect to the consolidated product inventory adjustment route
    from .product_inventory_routes import adjust_sku_inventory
    return adjust_sku_inventory(sku_id)
