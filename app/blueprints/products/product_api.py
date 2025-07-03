
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ...models import db, ProductSKU
from ...services.product_service import ProductService
from . import products_bp
from sqlalchemy import func

product_api_bp = Blueprint('product_api', __name__, url_prefix='/api')

@product_api_bp.route('/products')
@login_required
def get_products():
    """Get all products for dropdowns and autocomplete"""
    try:
        # Try new Product model first
        try:
            from ...models import Product
            products = Product.query.filter_by(
                is_active=True,
                organization_id=current_user.organization_id
            ).all()

            if products:  # If we have products in the new model, use those
                product_list = []
                for product in products:
                    product_list.append({
                        'id': product.id,
                        'name': product.name,
                        'product_base_unit': product.base_unit
                    })
                return jsonify(product_list)
        except ImportError:
            pass  # Fall back to legacy method

        # Legacy method - Get distinct product names from ProductSKU
        products = db.session.query(
            ProductSKU.product_name,
            func.min(ProductSKU.id).label('id'),
            ProductSKU.unit.label('product_base_unit')
        ).filter_by(
            is_active=True,
            organization_id=current_user.organization_id
        ).group_by(ProductSKU.product_name, ProductSKU.unit).all()

        product_list = []
        for product_row in products:
            product_list.append({
                'id': product_row.id,  # Use the first SKU ID as product ID
                'name': product_row.product_name,
                'product_base_unit': product_row.product_base_unit
            })

        return jsonify(product_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@product_api_bp.route('/products/<int:product_id>/variants')
@login_required
def get_product_variants(product_id):
    """Get variants for a specific product by ID"""
    try:
        # Try new model structure first
        try:
            from ...models import Product, ProductVariant
            product = Product.query.filter_by(
                id=product_id,
                organization_id=current_user.organization_id
            ).first()

            if product:
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
        except ImportError:
            pass  # Fall back to legacy method

        # Legacy method - Get product name from the SKU ID, then get variants
        base_sku = ProductSKU.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()
        
        if not base_sku:
            return jsonify({'error': 'Product not found'}), 404

        product_name = base_sku.product_name

        # Get all distinct variants for this product
        variants = db.session.query(
            ProductSKU.variant_name,
            func.min(ProductSKU.id).label('id')
        ).filter_by(
            product_name=product_name,
            is_active=True,
            organization_id=current_user.organization_id
        ).group_by(ProductSKU.variant_name).all()

        variant_list = []
        for variant_row in variants:
            variant_list.append({
                'id': variant_row.id,
                'name': variant_row.variant_name
            })

        return jsonify(variant_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@product_api_bp.route('/products/search')
@login_required
def search_products():
    """API endpoint for product search in finish batch modal"""
    query = request.args.get('q', '').strip()

    if len(query) < 2:
        return jsonify({'products': []})

    try:
        # Try new Product model first
        try:
            from ...models import Product
            products = Product.query.filter(
                Product.name.ilike(f'%{query}%'),
                Product.organization_id == current_user.organization_id,
                Product.is_active == True
            ).limit(10).all()

            if products:
                result = []
                for product in products:
                    result.append({
                        'id': product.id,
                        'name': product.name,
                        'product_base_unit': product.base_unit
                    })
                return jsonify({'products': result})
        except ImportError:
            pass

        # Legacy fallback
        products = db.session.query(
            ProductSKU.product_name,
            func.min(ProductSKU.id).label('id'),
            ProductSKU.unit.label('product_base_unit')
        ).filter(
            ProductSKU.product_name.ilike(f'%{query}%'),
            ProductSKU.is_active == True,
            ProductSKU.organization_id == current_user.organization_id
        ).group_by(ProductSKU.product_name, ProductSKU.unit).limit(10).all()

        result = []
        for product in products:
            result.append({
                'id': product.id,
                'name': product.product_name,
                'product_base_unit': product.product_base_unit
            })

        return jsonify({'products': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@product_api_bp.route('/products/add-from-batch', methods=['POST'])
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

@product_api_bp.route('/products/quick-add', methods=['POST'])
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
