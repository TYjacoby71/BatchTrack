from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Batch
from ...models.product import Product, ProductVariant
from ...services.product_service import ProductService
from ...services.inventory_adjustment import process_inventory_adjustment
from sqlalchemy import func

# Import the blueprint from __init__.py
from . import products_api_bp

@products_api_bp.route('/')
@login_required
def get_products():
    """Get all products for dropdowns and autocomplete"""
    try:
        # Get products using the Product model
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
        # Get the product with org scoping
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
                'name': variant.name,
                'description': variant.description or ''
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

    # Search products using the Product model
    products = Product.query.filter(
        Product.name.ilike(f'%{query}%'),
        Product.is_active == True,
        Product.organization_id == current_user.organization_id
    ).limit(10).all()

    result = []
    for product in products:
        result.append({
            'id': product.id,
            'name': product.name,
            'default_unit': product.base_unit
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

        return jsonify({
            'success': True,
            'product': {
                'id': sku.product.id,
                'name': sku.product.name,
                'product_base_unit': sku.product.base_unit
            },
            'variant': {
                'id': sku.variant.id,
                'name': sku.variant.name
            },
            'sku': {
                'id': sku.id,
                'name': sku.display_name
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# INVENTORY APIs
@products_api_bp.route('/inventory/add-from-batch', methods=['POST'])
@login_required
def add_inventory_from_batch():
    """Add product inventory from finished batch"""
    data = request.get_json()

    batch_id = data.get('batch_id')
    product_id = data.get('product_id')
    variant_id = data.get('variant_id')
    quantity = data.get('quantity')
    size_label = data.get('size_label', 'Bulk')

    if not batch_id or not product_id or not variant_id:
        return jsonify({'error': 'Batch ID, Product ID, and Variant ID are required'}), 400

    try:
        # Get product and variant with org scoping
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not product:
            return jsonify({'error': 'Product not found'}), 404

        variant = ProductVariant.query.filter_by(
            id=variant_id,
            product_id=product_id
        ).first()

        if not variant:
            return jsonify({'error': 'Variant not found'}), 404

        # Get or create the SKU
        sku = ProductService.get_or_create_sku(
            product_name=product.name,
            variant_name=variant.name,
            size_label=size_label,
            unit=product.base_unit
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

@products_api_bp.route('/sku/<int:sku_id>/adjust', methods=['POST'])
@login_required
def adjust_sku_inventory(sku_id):
    """Adjust SKU inventory via API"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()

    if not sku:
        return jsonify({'error': 'SKU not found'}), 404

    data = request.get_json()

    quantity = data.get('quantity')
    change_type = data.get('change_type')
    notes = data.get('notes')

    try:
        # Get additional product-specific parameters
        customer = data.get('customer')
        sale_price = data.get('sale_price')
        order_id = data.get('order_id')

        # Convert sale_price to float if provided
        sale_price_float = None
        if sale_price:
            try:
                sale_price_float = float(sale_price)
            except (ValueError, TypeError):
                pass

        # Use centralized inventory adjustment service
        success = process_inventory_adjustment(
            item_id=sku_id,
            quantity=quantity,
            change_type=change_type,
            unit=sku.unit,
            notes=notes,
            created_by=current_user.id,
            item_type='sku',
            customer=customer,
            sale_price=sale_price_float,
            order_id=order_id
        )

        if success:
            return jsonify({
                'success': True,
                'message': 'SKU inventory adjusted successfully',
                'new_quantity': sku.current_quantity
            })
        else:
            return jsonify({'error': 'Error adjusting inventory'}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/sku/<int:sku_id>')
@login_required
def get_sku_details(sku_id):
    """Get SKU details"""
    sku = ProductSKU.query.filter_by(
        id=sku_id,
        organization_id=current_user.organization_id
    ).first()

    if not sku:
        return jsonify({'error': 'SKU not found'}), 404

    return jsonify({
        'id': sku.id,
        'sku_code': sku.sku_code,
        'display_name': sku.display_name,
        'product_name': sku.product.name,
        'variant_name': sku.variant.name,
        'size_label': sku.size_label,
        'unit': sku.unit,
        'current_quantity': sku.current_quantity,
        'low_stock_threshold': sku.low_stock_threshold,
        'is_low_stock': sku.is_low_stock,
        'stock_status': sku.stock_status
    })

@products_api_bp.route('/product/<int:product_id>/skus')
@login_required
def get_product_skus(product_id):
    """Get all SKUs for a product"""
    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:
        return jsonify({'error': 'Product not found'}), 404

    skus = ProductSKU.query.filter_by(
        product_id=product_id,
        is_active=True,
        organization_id=current_user.organization_id
    ).all()

    sku_list = []
    for sku in skus:
        sku_list.append({
            'id': sku.id,
            'sku_code': sku.sku_code,
            'display_name': sku.display_name,
            'variant_name': sku.variant.name,
            'size_label': sku.size_label,
            'unit': sku.unit,
            'current_quantity': sku.current_quantity,
            'stock_status': sku.stock_status
        })

    return jsonify(sku_list)

@products_api_bp.route('/api/<int:product_id>/variants', methods=['GET'])
@login_required  
def get_product_variants_api(product_id):
    """Get all variants for a product"""
    try:
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not product:
            return jsonify({'error': 'Product not found'}), 404

        variants = ProductVariant.query.filter_by(
            product_id=product_id,
            is_active=True
        ).all()

        variant_data = []
        for variant in variants:
            variant_data.append({
                'id': variant.id,
                'name': variant.name,
                'description': variant.description,
                'color': variant.color,
                'size': variant.size,
                'material': variant.material,
                'scent': variant.scent
            })

        return jsonify({
            'status': 'success',
            'variants': variant_data
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@products_api_bp.route('/api/<int:product_id>/skus', methods=['GET'])
@login_required
def get_product_skus_api(product_id):
    """Get all SKUs for a product"""
    try:
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not product:
            return jsonify({'error': 'Product not found'}), 404

        skus = ProductSKU.query.filter_by(
            product_id=product_id,
            organization_id=current_user.organization_id
        ).all()

        sku_data = []
        for sku in skus:
            sku_data.append({
                'id': sku.id,
                'sku': sku.sku,
                'variant_name': sku.variant.name if sku.variant else 'Base',
                'size_label': sku.size_label,
                'unit': sku.unit,
                'quantity': sku.quantity or 0,
                'cost_per_unit': float(sku.cost_per_unit) if sku.cost_per_unit else 0.0
            })

        return jsonify({
            'status': 'success',
            'skus': sku_data
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500