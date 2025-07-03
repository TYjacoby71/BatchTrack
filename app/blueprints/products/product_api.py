from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU
from ...services.product_service import ProductService
from sqlalchemy import func

product_api_bp = Blueprint('product_api', __name__, url_prefix='/api/products')

@product_api_bp.route('/')
@login_required
def get_products():
    """Get all products for dropdowns and autocomplete"""
    try:
        # Get distinct product names from ProductSKU
        products = db.session.query(ProductSKU.product_name, ProductSKU.unit).distinct().filter_by(
            is_active=True,
            organization_id=current_user.organization_id
        ).all()

        product_list = []
        for product_name, base_unit in products:
            product_list.append({
                'name': product_name,
                'product_base_unit': base_unit
            })

        return jsonify(product_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@product_api_bp.route('/<product_name>/variants')
@login_required
def get_product_variants(product_name):
    """Get variants for a specific product"""
    try:
        variants = db.session.query(
            ProductSKU.variant_name,
            func.min(ProductSKU.id).label('id')
        ).filter_by(
            product_name=product_name,
            is_active=True,
            organization_id=current_user.organization_id
        ).group_by(ProductSKU.variant_name).all()

        variant_list = []
        for variant_name, sku_id in variants:
            variant_list.append({
                'id': sku_id,
                'name': variant_name
            })

        return jsonify(variant_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@product_api_bp.route('/search')
@login_required
def search_products():
    """Search products by name"""
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
    for product_name, product_base_unit in products:
        result.append({
            'name': product_name,
            'default_unit': product_base_unit
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

        # Use the inventory adjustment service to add inventory
        from ...services.inventory_adjustment import process_inventory_adjustment

        success = process_inventory_adjustment(
            item_id=sku.id,
            quantity=quantity,
            change_type='batch_completion',
            unit=sku.unit,
            notes=f'Added from batch {batch_id}',
            batch_id=batch_id,
            created_by=current_user.id,
            item_type='sku'
        )

        if success:
            db.session.commit()
            return jsonify({
                'success': True,
                'sku_id': sku.id,
                'message': f'Added {quantity} {sku.unit} to {sku.display_name}'
            })
        else:
            return jsonify({'error': 'Failed to add inventory'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@product_api_bp.route('/quick-add', methods=['POST'])
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