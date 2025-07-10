from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Product, ProductVariant
from ...services.product_service import ProductService
from sqlalchemy import func

# Define the blueprint
products_api_bp = Blueprint('products_api', __name__, url_prefix='/api/products')

@products_api_bp.route('/sku/<int:sku_id>/product')
@login_required
def get_product_from_sku(sku_id):
    """Get the Product ID from a SKU ID"""
    try:
        sku = ProductSKU.query.filter_by(
            id=sku_id,
            organization_id=current_user.organization_id
        ).first()

        if not sku:
            return jsonify({'error': 'SKU not found'}), 404

        if not sku.product_id:
            return jsonify({'error': 'SKU has no associated product'}), 404

        return jsonify({
            'product_id': sku.product_id,
            'sku_id': sku.id
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/')
@login_required
def get_products():
    """Get all products for dropdowns and autocomplete"""
    try:
        from ...models.product import Product

        # Get products using the proper Product model
        products = Product.query.filter_by(
            is_active=True,
            organization_id=current_user.organization_id
        ).all()

        product_list = []
        for product in products:
            product_list.append({
                'id': product.id,
                'name': product.name,
                'product_base_unit': product.base_unit
            })

        return jsonify(product_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/<int:product_id>/variants')
@login_required
def get_product_variants(product_id):
    """Get all variants for a specific product"""
    try:
        # Get all variants for this product that belong to current user's organization
        variants = ProductVariant.query.join(Product).filter(
            ProductVariant.product_id == product_id,
            Product.organization_id == current_user.organization_id,
            ProductVariant.is_active == True
        ).all()

        variant_list = []
        for variant in variants:
            variant_list.append({
                'id': variant.id,
                'name': variant.name,
                'description': variant.description
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
def search_products():
    """Search products by name"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': []})

    # Search for unique product names with their base SKU ID
    products = db.session.query(
        func.min(ProductSKU.id).label('product_id'),
        ProductSKU.product_name,
        ProductSKU.unit.label('product_base_unit')
    ).filter(
        ProductSKU.product_name.ilike(f'%{query}%'),
        ProductSKU.is_product_active == True,
        ProductSKU.is_active == True,
        ProductSKU.organization_id == current_user.organization_id
    ).group_by(ProductSKU.product_name, ProductSKU.unit).limit(10).all()

    result = []
    for product_id, product_name, product_base_unit in products:
        result.append({
            'id': product_id,
            'name': product_name,
            'default_unit': product_base_unit
        })

    return jsonify({'products': result})

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
        # Get or create the SKU with organization scoping
        sku = ProductService.get_or_create_sku(
            product_name=product_name,
            variant_name=variant_name or 'Base',
            size_label='Bulk',
            unit=product_base_unit
        )

        # Ensure the SKU belongs to the current user's organization
        if not sku.organization_id:
            sku.organization_id = current_user.organization_id

        db.session.commit()

        # Find the base product ID (first SKU for this product)
        base_sku = db.session.query(func.min(ProductSKU.id)).filter_by(
            product_name=sku.product_name,
            organization_id=current_user.organization_id
        ).scalar()

        return jsonify({
            'success': True,
            'product': {
                'id': base_sku,
                'name': sku.product_name,
                'product_base_unit': sku.unit
            },
            'variant': {
                'id': sku.id,
                'name': sku.variant_name
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# INVENTORY APIs
# Batch inventory additions are handled by product_inventory_routes.py

# Inventory adjustments are handled by product_inventory_routes.py

@products_api_bp.route('/products/variants/<int:variant_id>/sizes')
@login_required
def get_variant_sizes(variant_id):
    """Get all size labels for a specific variant"""
    try:
        # Get all SKUs for this variant that belong to current user's organization
        skus = ProductSKU.query.join(Product).filter(
            ProductSKU.variant_id == variant_id,
            Product.organization_id == current_user.organization_id,
            ProductSKU.is_active == True
        ).all()

        sizes = []
        for sku in skus:
            sizes.append({
                'size_label': sku.size_label,
                'sku_id': sku.id
            })

        return jsonify(sizes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# This API file only provides data retrieval and simple operations