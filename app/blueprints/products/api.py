from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Batch
from ...services.product_service import ProductService
from ...services.inventory_adjustment import process_inventory_adjustment
from sqlalchemy import func

# Import the blueprint from __init__.py
from . import products_api_bp

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
    """Get variants for a specific product by ID"""
    try:
        from ...models.product import Product, ProductVariant

        # Get the product with org scoping - no legacy support
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not product:
            return jsonify({'error': 'Product not found'}), 404

        # Get active variants for this product
        variants = ProductVariant.query.filter_by(
            product_id=product.id,
            is_active=True
        ).all()

        variant_list = []
        for variant in variants:
            variant_list.append({
                'id': variant.id,
                'name': variant.name
            })

        return jsonify(variant_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/search')
@login_required
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
@products_api_bp.route('/inventory/add-from-batch', methods=['POST'])
@login_required
def add_inventory_from_batch():
    """Add product inventory from finished batch - SINGLE ENDPOINT"""
    data = request.get_json()

    batch_id = data.get('batch_id')
    product_id = data.get('product_id')  # Changed from product_name
    product_name = data.get('product_name')  # Keep as fallback
    variant_name = data.get('variant_name')
    size_label = data.get('size_label')
    quantity = data.get('quantity')

    if not batch_id or (not product_id and not product_name):
        return jsonify({'error': 'Batch ID and Product ID or Name are required'}), 400

    try:
        # Get product name from ID if provided - with org scoping
        if product_id:
            base_sku = ProductSKU.query.filter_by(
                id=product_id,
                organization_id=current_user.organization_id
            ).first()
            if not base_sku:
                return jsonify({'error': 'Product not found'}), 404
            product_name = base_sku.product_name

        # Get or create the SKU
        sku = ProductService.get_or_create_sku(
            product_name=product_name,
            variant_name=variant_name or 'Base',
            size_label=size_label or 'Bulk'
        )

        # Use the inventory adjustment service to add inventory
        success = process_inventory_adjustment(
            item_id=sku.id,
            quantity=quantity,
            change_type='batch_completion',
            unit=sku.unit,
            notes=f'Added from batch {batch_id}',
            batch_id=batch_id,
            created_by=current_user.id,
            item_type='product'
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

@products_api_bp.route('/sku/<int:sku_id>/adjust', methods=['POST'])
@login_required
def adjust_sku_inventory(sku_id):
    """Legacy API route - redirect to consolidated product inventory adjustment"""
    from ..product_inventory_routes import api_adjust_sku_inventory
    return api_adjust_sku_inventory(sku_id)