from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU
from ...services.product_service import ProductService
from . import products_bp

product_api_bp = Blueprint('product_api', __name__, url_prefix='/products/api')

@product_api_bp.route('/<product_name>/variants', methods=['GET'])
@login_required
def get_product_variants(product_name):
    """API endpoint to get variants for a specific product"""
    # Get all SKUs for this product name
    skus = ProductSKU.query.filter_by(product_name=product_name, is_product_active=True).all()

    if not skus:
        return jsonify({'error': 'Product not found'}), 404

    variants = []
    seen_variants = set()

    for sku in skus:
        if sku.variant_name not in seen_variants:
            variants.append({
                'id': sku.id,
                'name': sku.variant_name,
                'sku': sku.sku_code
            })
            seen_variants.add(sku.variant_name)

    # Add default variant if no variants exist
    if not variants:
        variants.append({
            'id': None,
            'name': 'Default',
            'sku': None
        })

    return jsonify({'variants': variants})

@product_api_bp.route('/search')
@login_required
def search_products():
    """API endpoint for product search in finish batch modal - returns only parent products"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': []})

    # Search for unique product names only
    products = db.session.query(
        ProductSKU.product_name,
        ProductSKU.unit.label('product_base_unit')
    ).filter(
        ProductSKU.product_name.ilike(f'%{query}%'),
        ProductSKU.is_product_active == True,
        ProductSKU.is_active == True,
        ProductSKU.organization_id == current_user.organization_id
    ).distinct(ProductSKU.product_name).limit(10).all()

    result = []
    for product in products:
        result.append({
            'name': product.product_name,
            'default_unit': product.product_base_unit
        })

    return jsonify({'products': result})

@product_api_bp.route('/add-from-batch', methods=['POST'])
@login_required
def add_from_batch():
    """Add product inventory from finished batch"""
    data = request.get_json()

    batch_id = data.get('batch_id')
    product_name = data.get('product_name')
    variant_name = data.get('variant_name')
    size_label = data.get('size_label')
    quantity = data.get('quantity')

    if not batch_id or not product_name:
        return jsonify({'error': 'Batch ID and Product Name are required'}), 400

    try:
        # Get or create the SKU
        sku = ProductService.get_or_create_sku(
            product_name=product_name,
            variant_name=variant_name or 'Base',
            size_label=size_label or 'Bulk'
        )

        # Add inventory to the SKU
        inventory = ProductService.add_product_from_batch(
            batch_id=batch_id,
            sku_id=sku.id,
            quantity=quantity
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'inventory_id': inventory.id,
            'message': f'Added {quantity} {sku.unit} to {sku.display_name}'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product_api_bp.route('/quick-add', methods=['POST'])
@login_required
def quick_add_product():
    """Quick add product and/or variant for finish batch modal"""
    data = request.get_json()

    product_name = data.get('product_name')
    variant_name = data.get('variant_name')
    product_base_unit = data.get('product_base_unit', 'oz')

    if not product_name:
        return jsonify({'error': 'Product name is required'}), 400

    try:
        # Get or create the SKU
        sku = ProductService.get_or_create_sku(
            product_name=product_name,
            variant_name=variant_name or 'Base',
            size_label='Bulk',
            unit=product_base_unit
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'product': {
                'name': sku.product_name,
                'product_base_unit': sku.product_base_unit
            },
            'variant': {
                'id': sku.id,
                'name': sku.variant_name
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500