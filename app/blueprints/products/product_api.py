from flask import Blueprint, jsonify, request
from flask_login import login_required
from ...models import db, Product, ProductVariation
from ...services.product_service import ProductService
from . import products_bp

product_api_bp = Blueprint('product_api', __name__, url_prefix='/products/api')

@product_api_bp.route('/<int:product_id>/variants', methods=['GET'])
@login_required
def get_product_variants(product_id):
    """API endpoint to get variants for a specific product"""
    product = Product.query.get_or_404(product_id)

    variants = []
    for variant in product.variations:
        variants.append({
            'id': variant.id,
            'name': variant.name,
            'sku': variant.sku
        })

    # Add default variant if no variants exist
    if not variants:
        variants.append({
            'id': None,
            'name': 'Default',
            'sku': None
        })

    return jsonify({'variants': variants})

@product_api_bp.route('/search', methods=['GET'])
@login_required
def search_products():
    """API endpoint for product/variant search in finish batch modal"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': []})

    # Search products by name
    products = Product.query.filter(
        Product.name.ilike(f'%{query}%'),
        Product.is_active == True
    ).limit(10).all()

    result = []
    for product in products:
        product_data = {
            'id': product.id,
            'name': product.name,
            'default_unit': product.product_base_unit,
            'variants': []
        }

        # Add existing variants
        for variant in product.variations:
            product_data['variants'].append({
                'id': variant.id,
                'name': variant.name,
                'sku': variant.sku
            })

        # Add Base variant if no variants exist
        if not product.variations:
            product_data['variants'].append({
                'id': None,
                'name': 'Base',
                'sku': None
            })

        result.append(product_data)

    return jsonify({'products': result})

@product_api_bp.route('/add-from-batch', methods=['POST'])
@login_required
def add_from_batch():
    """Add product inventory from finished batch"""
    data = request.get_json()

    batch_id = data.get('batch_id')
    product_id = data.get('product_id') 
    variant_label = data.get('variant_label')
    size_label = data.get('size_label')
    quantity = data.get('quantity')

    if not batch_id or not product_id:
        return jsonify({'error': 'Batch ID and Product ID are required'}), 400

    try:
        inventory = ProductService.add_product_from_batch(
            batch_id=batch_id,
            product_id=product_id,
            variant_label=variant_label,
            size_label=size_label,
            quantity=quantity
        )

        db.session.commit()

        return jsonify({
            'success': True,
            'inventory_id': inventory.id,
            'message': f'Added {inventory.quantity} {inventory.unit} to product inventory'
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

    # Check if product exists
    product = Product.query.filter_by(name=product_name).first()

    if not product:
        # Create new product
        product = Product(
            name=product_name,
            product_base_unit=product_base_unit
        )
        db.session.add(product)
        db.session.flush()  # Get the ID

    variant = None
    if variant_name and variant_name.lower() != 'default':
        # Check if variant exists
        variant = ProductVariation.query.filter_by(
            product_id=product.id, 
            name=variant_name
        ).first()

        if not variant:
            # Create new variant
            variant = ProductVariation(
                product_id=product.id,
                name=variant_name
            )
            db.session.add(variant)
            db.session.flush()

    db.session.commit()

    return jsonify({
        'success': True,
        'product': {
            'id': product.id,
            'name': product.name,
            'product_base_unit': product.product_base_unit
        },
        'variant': {
            'id': variant.id if variant else None,
            'name': variant.name if variant else 'Default'
        } if variant or variant_name else None
    })