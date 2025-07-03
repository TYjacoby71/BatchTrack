
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU, Batch
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
        # Get distinct products with their first SKU ID as product identifier
        products = db.session.query(
            func.min(ProductSKU.id).label('product_id'),
            ProductSKU.product_name, 
            ProductSKU.unit
        ).filter_by(
            is_active=True,
            organization_id=current_user.organization_id
        ).group_by(ProductSKU.product_name, ProductSKU.unit).all()

        product_list = []
        for product_id, product_name, base_unit in products:
            product_list.append({
                'id': product_id,
                'name': product_name,
                'product_base_unit': base_unit
            })

        return jsonify(product_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/<int:product_id>/variants')
@login_required
def get_product_variants(product_id):
    """Get variants for a specific product by ID"""
    try:
        # Get the product name from the product_id (first SKU) - with org scoping
        base_sku = ProductSKU.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()
        
        if not base_sku:
            return jsonify({'error': 'Product not found'}), 404
            
        product_name = base_sku.product_name
        
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
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, Product, ProductVariant, ProductSKU

products_api_bp = Blueprint('products_api', __name__, url_prefix='/products/api')

@products_api_bp.route('/<int:product_id>/variants')
@login_required
def get_product_variants(product_id):
    """Get all variants for a specific product"""
    try:
        # Get the product with organization scoping
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()
        
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        
        # Get all variants for this product
        variants = ProductVariant.query.filter_by(
            product_id=product_id,
            is_active=True,
            organization_id=current_user.organization_id
        ).all()
        
        variant_data = []
        for variant in variants:
            variant_data.append({
                'id': variant.id,
                'name': variant.name,
                'description': variant.description,
                'is_active': variant.is_active
            })
        
        return jsonify({
            'variants': variant_data,
            'product_name': product.name
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@products_api_bp.route('/<int:product_id>/skus')
@login_required 
def get_product_skus(product_id):
    """Get all SKUs for a specific product"""
    try:
        # Get all SKUs for this product with organization scoping
        skus = ProductSKU.query.filter_by(
            product_id=product_id,
            is_active=True,
            organization_id=current_user.organization_id
        ).all()
        
        sku_data = []
        for sku in skus:
            sku_data.append({
                'id': sku.id,
                'sku_code': sku.sku_code,
                'size_label': sku.size_label,
                'variant_id': sku.variant_id,
                'variant_name': sku.variant.name if sku.variant else sku.variant_name,
                'current_quantity': sku.current_quantity,
                'unit': sku.unit
            })
        
        return jsonify({
            'skus': sku_data
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
