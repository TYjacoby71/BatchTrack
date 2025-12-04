from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU
from ...services.product_service import ProductService
from sqlalchemy import func

# Define the blueprint
products_api_bp = Blueprint('products_api', __name__, url_prefix='/api/products')

@products_api_bp.route('/sku/<int:sku_id>/product')
@login_required
def get_product_from_sku(sku_id):
    """Get the Product ID from a SKU ID"""
    try:
        result = ProductService.get_product_from_sku(sku_id)
        if not result:
            return jsonify({'error': 'SKU not found or no associated product'}), 404
        
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/')
@login_required
def get_products():
    """Get all products for dropdowns and autocomplete"""
    try:
        products = ProductService.get_all_products()
        return jsonify(products)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/<int:product_id>/variants')
@login_required
def get_product_variants(product_id):
    """Get variants for a specific product by ID"""
    try:
        # Use ProductService to get variants safely with organization scoping
        variants = ProductService.get_product_variants(product_id)

        if variants is None:
            return jsonify({'error': 'Product not found'}), 404

        variant_list = []
        for variant in variants:
            variant_list.append({
                'id': variant.id,
                'name': variant.name
            })

        return jsonify({'variants': variant_list})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/search')
@login_required
def search_products():
    """Search SKUs by product name, variant, or size label"""
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify([])
    
    try:
        skus = ProductService.search_skus(search_term)
        results = []
        for sku in skus:
            results.append({
                'sku_id': sku.id,
                'sku_code': sku.sku_code,
                'product_name': sku.product.name,
                'variant_name': sku.variant.name,
                'size_label': sku.size_label,
                'current_quantity': float(sku.current_quantity or 0),
                'unit': sku.unit
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/low-stock')
@login_required
def get_low_stock():
    """Get SKUs that are low on stock"""
    threshold_multiplier = float(request.args.get('threshold', 1.0))
    
    try:
        low_stock_skus = ProductService.get_low_stock_skus(threshold_multiplier)
        results = []
        for sku in low_stock_skus:
            results.append({
                'sku_id': sku.id,
                'sku_code': sku.sku_code,
                'product_name': sku.product.name,
                'variant_name': sku.variant.name,
                'size_label': sku.size_label,
                'current_quantity': float(sku.current_quantity or 0),
                'low_stock_threshold': float(sku.low_stock_threshold or 0),
                'unit': sku.unit
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/<int:product_id>/inventory-summary')
@login_required
def get_product_inventory_summary_api(product_id):
    """Get inventory summary for a specific product"""
    try:
        summary = ProductService.get_product_inventory_summary(product_id)
        if not summary:
            return jsonify({'error': 'Product not found'}), 404
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@products_api_bp.route('/quick-add', methods=['POST'])
@login_required
def quick_add_product():
    """Quick add product and/or variant"""
    data = request.get_json()

    product_name = data.get('product_name')
    variant_name = data.get('variant_name')
    product_base_unit = data.get('product_base_unit', 'oz')

    if not product_name:
        return jsonify({'error': 'Product name is required'}), 400

    try:
        result = ProductService.quick_add_product(
            product_name=product_name,
            variant_name=variant_name or 'Base',
            product_base_unit=product_base_unit
        )
        
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# INVENTORY APIs
# Batch inventory additions are handled by product_inventory_routes.py

# Inventory adjustments are handled by product_inventory_routes.py
# This API file only provides data retrieval and simple operations

