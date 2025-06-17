
from flask import jsonify, request
from flask_login import login_required
from ...extensions import db
from ...models import Product, ProductInventory
from services.product_service import ProductService
from . import products_bp

@products_bp.route('/api/products', methods=['GET'])
@login_required
def api_get_products():
    """API endpoint to get all products"""
    products = Product.query.all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'product_base_unit': p.product_base_unit
    } for p in products])

@products_bp.route('/api/products/<int:product_id>/inventory', methods=['GET'])
@login_required
def api_get_product_inventory(product_id):
    """API endpoint to get product inventory"""
    inventory_groups = ProductService.get_fifo_inventory_groups(product_id)
    return jsonify(inventory_groups)

@products_bp.route('/api/products/<int:product_id>/variants', methods=['GET'])
@login_required
def api_get_product_variants(product_id):
    """API endpoint to get product variants"""
    from ...models import ProductVariation
    
    variants = ProductVariation.query.filter_by(product_id=product_id).all()
    return jsonify([{
        'id': v.id,
        'name': v.name,
        'description': v.description
    } for v in variants])
