from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ...models import db, ProductSKU, InventoryItem
from ...services.product_service import ProductService
from ...utils.unit_utils import get_global_unit_list

# Create the product variants blueprint
product_variants_bp = Blueprint('product_variants', __name__)

@product_variants_bp.route('/<int:product_id>/variants/new', methods=['POST'])
@login_required
def add_variant(product_id):
    """Quick add new product variant via AJAX"""
    try:
        from ...models.product import Product, ProductVariant, ProductSKU
        
        # First try to get the Product record
        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first()
        
        # If no Product record exists, try to find it via ProductSKU and create Product
        if not product:
            # Look for existing SKU with this product_id
            base_sku = ProductSKU.query.filter_by(
                id=product_id,
                organization_id=current_user.organization_id
            ).first()
            
            if not base_sku:
                return jsonify({'error': 'Product not found'}), 404
            
            # For legacy data, the product_id in the URL might be a SKU ID
            # Try to find or create the actual Product record
            if base_sku.product_id:
                product = Product.query.get(base_sku.product_id)
            
            if not product:
                return jsonify({'error': 'Product record not found'}), 404
        
        # Get variant name from request
        if request.is_json:
            data = request.get_json()
            variant_name = data.get('name')
            description = data.get('description')
        else:
            variant_name = request.form.get('name')
            description = request.form.get('description')

        if not variant_name or variant_name.strip() == '':
            return jsonify({'error': 'Variant name is required'}), 400

        variant_name = variant_name.strip()

        # Check if variant already exists for this product
        existing_variant = ProductVariant.query.filter_by(
            product_id=product.id,
            name=variant_name
        ).first()

        if existing_variant:
            return jsonify({'error': f'Variant "{variant_name}" already exists for this product'}), 400

        # Create the ProductVariant first
        new_variant = ProductVariant(
            product_id=product.id,
            name=variant_name,
            description=description,
            organization_id=current_user.organization_id
        )
        db.session.add(new_variant)
        db.session.flush()  # Get the variant ID without committing

        # Generate SKU code using the service
        from ...services.product_service import ProductService
        sku_code = ProductService.generate_sku_code(product.name, variant_name, 'Bulk')
        
        # Create the ProductSKU for this variant
        new_sku = ProductSKU(
            product_id=product.id,
            variant_id=new_variant.id,
            size_label='Bulk',
            sku_code=sku_code,
            unit=product.base_unit,
            low_stock_threshold=product.low_stock_threshold,
            description=description,
            current_quantity=0.0,
            is_active=True,
            is_product_active=True,
            organization_id=current_user.organization_id,
            created_by=current_user.id
        )
        db.session.add(new_sku)
        db.session.commit()

        return jsonify({
            'success': True,
            'variant': {
                'id': new_variant.id,
                'name': new_variant.name,
                'sku_id': new_sku.id,
                'sku': new_sku.sku_code,
                'unit': new_sku.unit,
                'size_label': new_sku.size_label
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to create variant: {str(e)}'}), 500

@product_variants_bp.route('/<int:product_id>/variant/<variant_name>')
@login_required
def view_variant(product_id, variant_name):
    """View individual product variation details"""
    # Get the product using the new Product model
    from ...models.product import Product, ProductVariant
    
    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))
    
    # Get the variant by name
    variant = ProductVariant.query.filter_by(
        product_id=product.id,
        name=variant_name
    ).first()
    
    if not variant:
        flash('Variant not found', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))
    
    # Get all SKUs for this product/variant combination with proper organization scoping
    from sqlalchemy.orm import joinedload
    skus = ProductSKU.query.options(
        joinedload(ProductSKU.inventory_item)
    ).filter_by(
        product_id=product.id,
        variant_id=variant.id,
        is_active=True,
        organization_id=current_user.organization_id
    ).all()

    if not skus:
        flash('Variant not found', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Group SKUs by size_label - derive totals from authoritative inventory data
    size_groups = {}
    for sku in skus:
        display_size_label = sku.size_label or "Bulk"
        key = f"{display_size_label}_{sku.unit}"

        if key not in size_groups:
            size_groups[key] = {
                'size_label': display_size_label,
                'unit': sku.unit,
                'total_quantity': 0.0,
                'skus': []
            }

        # Always derive from inventory_item.quantity as the single source of truth
        current_quantity = 0.0
        if sku.inventory_item and sku.inventory_item.quantity is not None:
            current_quantity = float(sku.inventory_item.quantity)
        
        size_groups[key]['total_quantity'] += current_quantity
        size_groups[key]['skus'].append(sku)

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    return render_template('products/view_variation.html',
                         product=product,
                         product_name=product.name,
                         variant_name=variant.name,
                         variation=variant,
                         variant_description=variant.description,
                         size_groups=size_groups,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list)

@product_variants_bp.route('/<int:product_id>/variant/<variant_name>/edit', methods=['POST'])
@login_required
def edit_variant(product_id, variant_name):
    """Edit product variation details"""
    from ...models.product import Product, ProductVariant
    
    # Get the product using the new Product model
    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))
    
    # Get the variant
    variant = ProductVariant.query.filter_by(
        product_id=product.id,
        name=variant_name
    ).first()
    
    if not variant:
        flash('Variant not found', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))
    
    name = request.form.get('name')
    description = request.form.get('description')

    if not name:
        flash('Variant name is required', 'error')
        return redirect(url_for('products.view_variant', 
                               product_id=product_id, 
                               variant_name=variant_name))

    # Check if another variant has this name for the same product
    existing = ProductVariant.query.filter(
        ProductVariant.product_id == product.id,
        ProductVariant.name == name,
        ProductVariant.id != variant.id
    ).first()

    if existing:
        flash('Another variant with this name already exists for this product', 'error')
        return redirect(url_for('products.view_variant', 
                               product_id=product_id, 
                               variant_name=variant_name))

    # Update the variant
    variant.name = name
    variant.description = description

    db.session.commit()
    flash('Variant updated successfully', 'success')

    return redirect(url_for('products.view_variant', 
                           product_id=product_id, 
                           variant_name=name))

@product_variants_bp.route('/<int:product_id>/variant/<variant_name>/delete', methods=['POST'])
@login_required
def delete_variant(product_id, variant_name):
    """Delete a product variant and all its SKUs"""
    from ...models.product import Product, ProductVariant
    
    # Get the product using the new Product model
    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()
    
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))
    
    # Get the variant
    variant = ProductVariant.query.filter_by(
        product_id=product.id,
        name=variant_name
    ).first()
    
    if not variant:
        flash('Variant not found', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))
    
    # Get all SKUs for this variant
    skus = ProductSKU.query.filter_by(
        product_id=product.id,
        variant_id=variant.id,
        organization_id=current_user.organization_id
    ).all()

    if not skus:
        flash('Variant not found', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Check if any SKUs have inventory
    has_inventory = any(sku.current_quantity > 0 for sku in skus)
    if has_inventory:
        flash('Cannot delete variant with existing inventory', 'error')
        return redirect(url_for('products.view_variant', 
                               product_id=product_id, 
                               variant_name=variant_name))

    # Delete the variant and its SKUs
    variant.is_active = False
    for sku in skus:
        sku.is_active = False

    db.session.commit()

    # Check if this was the last variant for the product
    remaining_variants = ProductVariant.query.filter_by(
        product_id=product.id,
        is_active=True
    ).count()

    if remaining_variants == 0:
        # Create a Base variant
        base_variant = ProductVariant(
            product_id=product.id,
            name='Base',
            description='Default base variant',
            organization_id=current_user.organization_id
        )
        db.session.add(base_variant)
        db.session.commit()
        flash(f'Variant "{variant_name}" deleted. Created default "Base" variant.', 'success')
    else:
        flash(f'Variant "{variant_name}" deleted successfully', 'success')

    return redirect(url_for('products.view_product', product_id=product_id))