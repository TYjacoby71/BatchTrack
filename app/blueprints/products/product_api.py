
from flask import jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Product, ProductVariant
from ...services.product_service import ProductService
from . import products_bp
from sqlalchemy import func

@products_bp.route('/api/products')
@login_required
def get_products():
    """Get all products for dropdowns and autocomplete"""
    try:
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

@products_bp.route('/api/products/<int:product_id>/variants')
@login_required
def get_product_variants(product_id):
    """Get variants for a specific product by ID"""
    try:
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not product:
            return jsonify({'error': 'Product not found'}), 404

        variants = product.variants.filter_by(is_active=True).all()
        variant_list = []
        for variant in variants:
            # Get the bulk SKU ID for this variant
            bulk_sku = variant.bulk_sku
            variant_list.append({
                'id': bulk_sku.id if bulk_sku else variant.id,
                'name': variant.name
            })
        return jsonify(variant_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_bp.route('/api/products/search')
@login_required
def search_products():
    """API endpoint for product search in finish batch modal"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': []})

    try:
        products = Product.query.filter(
            Product.name.ilike(f'%{query}%'),
            Product.organization_id == current_user.organization_id,
            Product.is_active == True
        ).limit(10).all()

        result = []
        for product in products:
            result.append({
                'id': product.id,
                'name': product.name,
                'product_base_unit': product.base_unit
            })

        return jsonify({'products': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_bp.route('/api/products/add-from-batch', methods=['POST'])
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

@products_bp.route('/api/products/quick-add', methods=['POST'])
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
                'id': sku.id,
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
