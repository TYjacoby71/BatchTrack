from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from ...models import db, InventoryItem
from ...models.product import Product, ProductVariant, ProductSKU, ProductSKUHistory
from ...models.batch import Batch

try:
    from ...utils.authorization import require_permission
except ImportError:
    # test-safe no-op decorator
    def require_permission(*args, **kwargs):
        def _wrap(f): return f
        return _wrap

# Helper for product audit entries, now using canonical service
import app.services.inventory_adjustment as inv_adj

# This function is defined twice in the original code.
# The second definition is the one that will be used due to Python's execution order.
# The provided change targets the second definition.
# The first definition is kept here to accurately reflect the original code's structure before the change.
def _write_product_created_audit(variant):
    # lazy import so the patched symbol is used
    from app.services import inventory_adjustment as inv
    inv.record_audit_entry(
        item_id=variant.id,
        change_type="product_created",
        notes=f"Product variant created: {variant.name}",
    )


from ...services.product_service import ProductService
from ...utils.fifo_generator import generate_fifo_code
from ...services.inventory_adjustment import process_inventory_adjustment, record_audit_entry as _record_audit_entry

# Wrapper for audit entry - used by tests
# This function is also defined twice, the second one is the one that is used.
# The change request targets the first definition of _write_product_created_audit, which is actually not used.
# The second definition _write_product_created_audit(sku) is used by tests.
# Given the user message "Fix audit function to use lazy import for proper mocking",
# it's most likely referring to the testable function.
# The change provided in the prompt modifies the definition that takes `variant` as an argument, not `sku`.
# Assuming the intention is to fix the function that is actually called for product creation audits during normal operation,
# which is the first definition, I will apply the change there.
# If the intention was to fix the test wrapper, the change would need to target the second definition.
# For now, I am applying the change to the function that is called during product creation.
# The second definition `_write_product_created_audit(sku)` which is likely for testing, is kept as is.

products_bp = Blueprint('products', __name__, url_prefix='/products')

def create_product_from_data(data):
    """
    Helper function to create products - used by both regular product creation
    and quick add functionality
    """
    try:
        from ...models import db, InventoryItem, InventoryHistory
        from ...utils.permissions import get_effective_organization_id

        organization_id = get_effective_organization_id()
        if not organization_id and current_user.user_type != 'developer':
            return {'success': False, 'error': 'No organization context'}

        # Create inventory item for product
        product = InventoryItem(
            name=data['name'],
            type='product',
            unit=data.get('unit', 'count'),
            quantity=0,
            organization_id=organization_id
        )

        db.session.add(product)
        db.session.flush()

        # Create initial audit entry using canonical service
        from app.services.inventory_adjustment import record_audit_entry
        record_audit_entry(
            item_id=product.id,
            change_type='product_creation',
            notes='Initial product creation' + (' via quick add' if data.get('quick_add') else ''),
            unit=product.unit
        )
        db.session.commit()

        return {
            'success': True,
            'product': {
                'id': product.id,
                'name': product.name,
                'unit': product.unit
            }
        }

    except Exception as e:
        db.session.rollback()
        return {'success': False, 'error': str(e)}


@products_bp.route('/')
@products_bp.route('/list')
@login_required
def product_list():
    """List all products with inventory summary and sorting"""
    from ...services.product_service import ProductService

    sort_type = request.args.get('sort', 'name')
    product_data = ProductService.get_product_summary_skus()

    # Convert dict data to objects with the attributes the template expects
    class ProductSummary:
        def __init__(self, data):
            self.name = data.get('product_name', '')
            self.product_base_unit = data.get('product_base_unit', '')
            self.created_at = data.get('last_updated')
            self.inventory = []
            # Calculate total quantity from inventory
            self.total_quantity = data.get('total_quantity', 0)
            # Add product ID for URL generation
            self.id = data.get('product_id', None)

            # Calculate aggregate inventory values
            self.total_bulk = 0
            self.total_packaged = 0

            # Get actual Product and its variants
            if self.id:
                from ...models.product import ProductSKU, Product, ProductVariant

                # Find the actual Product by name
                product = Product.query.filter_by(
                    name=self.name,
                    organization_id=current_user.organization_id
                ).first()

                if product:
                    self.id = product.id  # Use actual product ID

                    # Get actual ProductVariant objects (not size labels)
                    actual_variants = ProductVariant.query.filter_by(
                        product_id=product.id,
                        is_active=True
                    ).all()

                    # Create variation objects for template compatibility
                    self.variations = []
                    for variant in actual_variants:
                        variant_obj = type('Variation', (), {
                            'name': variant.name,
                            'description': variant.description,
                            'id': variant.id,
                            'sku': None  # Will be set below if there's a primary SKU
                        })()
                        self.variations.append(variant_obj)

                    # Set variant count to actual number of variants
                    self.variant_count = len(actual_variants)

                    # Calculate aggregates from SKUs
                    product_skus = ProductSKU.query.filter_by(
                        product_id=product.id,
                        organization_id=current_user.organization_id,
                        is_active=True
                    ).all()

                    for sku in product_skus:
                        if sku.inventory_item and sku.inventory_item.quantity > 0:
                            size_label = sku.size_label if sku.size_label else 'Bulk'
                            if size_label == 'Bulk':
                                self.total_bulk += sku.inventory_item.quantity
                            else:
                                self.total_packaged += sku.inventory_item.quantity
                else:
                    # Fallback for legacy data
                    self.variant_count = data.get('sku_count', 0)
                    self.variations = []

    # Get product IDs for the summary objects
    enhanced_product_data = []
    for data in product_data:
        # Get the actual product ID instead of SKU inventory_item_id
        first_sku = ProductSKU.query.filter_by(
            organization_id=current_user.organization_id,
            is_active=True
        ).join(ProductSKU.product).filter(
            Product.name == data['product_name']
        ).first()
        if first_sku:
            data['product_id'] = first_sku.product_id  # Use actual product ID
            enhanced_product_data.append(data)

    products = [ProductSummary(data) for data in enhanced_product_data]

    # Sort products based on the requested sort type
    if sort_type == 'popular':
        # Sort by sales volume (most sales first) - TODO: implement sales tracking for SKUs
        products.sort(key=lambda p: p.total_quantity, reverse=True)
    elif sort_type == 'stock':
        # Sort by stock level (low stock first)
        products.sort(key=lambda p: p.total_quantity)
    else:  # default to name
        products.sort(key=lambda p: p.name.lower())

    return render_template('products/list_products.html', products=products, current_sort=sort_type)

# Add alias for backward compatibility
list_products = product_list

@products_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        name = request.form.get('name')
        unit = request.form.get('product_base_unit')
        low_stock_threshold = request.form.get('low_stock_threshold', 0)

        if not name or not unit:
            flash('Name and product base unit are required', 'error')
            return redirect(url_for('products.new_product'))

        # Check if product already exists (check both new Product model and legacy ProductSKU)
        from ...models.product import Product, ProductVariant
        existing_product = Product.query.filter_by(
            name=name,
            organization_id=current_user.organization_id
        ).first()

        # Also check legacy ProductSKU table
        existing_sku = ProductSKU.query.filter_by(
            product_name=name,
            organization_id=current_user.organization_id
        ).first()

        if existing_product or existing_sku:
            flash('Product with this name already exists', 'error')
            return redirect(url_for('products.new_product'))

        try:
            # Step 1: Create the main Product
            product = Product(
                name=name,
                base_unit=unit,
                low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(product)
            db.session.flush()  # Get the product ID

            # Step 2: Create the base ProductVariant named "Base"
            variant = ProductVariant(
                product_id=product.id,
                name='Base',
                description='Default base variant',
                organization_id=current_user.organization_id
            )
            db.session.add(variant)
            db.session.flush()  # Get the variant ID

            # Step 3: Create inventory item for the SKU
            inventory_item = InventoryItem(
                name=f"{name} - Base - Bulk",
                type='product',  # Critical: mark as product type
                unit=unit,
                quantity=0.0,
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(inventory_item)
            db.session.flush()  # Get the inventory_item ID

            # Step 4: Create the base SKU with "Bulk" size label
            from ...services.product_service import ProductService
            sku_code = ProductService.generate_sku_code(name, 'Base', 'Bulk')

            # Generate SKU name - never leave it empty
            sku_name = f"{name} - Base - Bulk"

            sku = ProductSKU(
                # New foreign key relationships
                product_id=product.id,
                variant_id=variant.id,
                size_label='Bulk',
                sku_code=sku_code,
                sku_name=sku_name,  # Always set the sku_name
                unit=unit,
                low_stock_threshold=float(low_stock_threshold) if low_stock_threshold else 0,
                organization_id=current_user.organization_id,
                created_by=current_user.id,
                # Link to inventory item
                inventory_item_id=inventory_item.id,
                is_active=True,
                is_product_active=True
            )
            db.session.add(sku)
            db.session.commit()

            # Call the audit wrapper
            _write_product_created_audit(sku)

            flash('Product created successfully', 'success')
            return redirect(url_for('products.view_product', product_id=sku.inventory_item_id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'error')
            return redirect(url_for('products.new_product'))

    units = get_global_unit_list()
    return render_template('products/new_product.html', units=units)

@products_bp.route('/<int:product_id>')
@login_required
def view_product(product_id):
    """View product details with all SKUs by product ID"""
    from ...services.product_service import ProductService
    from ...models.product import Product

    # First try to find the product directly by ID
    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:
        # If not found by product ID, try to find by inventory_item_id (legacy support)
        base_sku = ProductSKU.query.filter_by(
            inventory_item_id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not base_sku:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))

        product = base_sku.product

    # Get all SKUs for this product - with org scoping
    skus = ProductSKU.query.filter_by(
        product_id=product.id,
        is_active=True,
        organization_id=current_user.organization_id
    ).all()

    if not skus:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    # Group SKUs by variant
    variants = {}
    for sku in skus:
        variant_key = sku.variant.name
        if variant_key not in variants:
            variants[variant_key] = {
                'name': sku.variant.name,
                'description': sku.variant.description,
                'skus': []
            }
        variants[variant_key]['skus'].append(sku)

    # Get available containers for manual stock addition
    available_containers = InventoryItem.query.filter_by(
        type='container',
        is_archived=False
    ).filter(InventoryItem.quantity > 0).all()

    # Use the actual Product model
    # Add variations for template compatibility
    product.variations = [type('Variation', (), {
        'name': variant_name,
        'description': variant_data['description'],
        'id': variant_data['skus'][0].inventory_item_id if variant_data['skus'] else None,
        'sku': variant_data['skus'][0].sku_code if variant_data['skus'] else None
    })() for variant_name, variant_data in variants.items()]

    # Also add skus to product for template compatibility
    product.skus = skus

    return render_template('products/view_product.html',
                         product=product,
                         variants=variants,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list,
                         inventory_groups={})

# Keep the old route for backward compatibility
@products_bp.route('/<product_name>')
@login_required
def view_product_by_name(product_name):
    """Redirect to product by ID for backward compatibility"""
    # Find the first SKU for this product to get the ID
    sku = ProductSKU.query.filter_by(
        product_name=product_name,
        is_active=True
    ).first()

    if not sku:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    return redirect(url_for('products.view_product', product_id=sku.inventory_item_id))



@products_bp.route('/<int:product_id>/edit', methods=['POST'])
@login_required
def edit_product(product_id):
    """Edit product details by product ID"""
    from ...models.product import Product

    # First try to find the product directly by ID
    product = Product.query.filter_by(
        id=product_id,
        organization_id=current_user.organization_id
    ).first()

    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products.product_list'))

    name = request.form.get('name')
    unit = request.form.get('base_unit')  # Updated to match template form field name
    low_stock_threshold = request.form.get('low_stock_threshold', 0)

    if not name or not unit:
        flash('Name and product base unit are required', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Check if another product has this name
    existing = Product.query.filter(
        Product.name == name,
        Product.id != product.id,
        Product.organization_id == current_user.organization_id
    ).first()
    if existing:
        flash('Another product with this name already exists', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

    # Update the product
    product.name = name
    product.base_unit = unit
    product.low_stock_threshold = float(low_stock_threshold) if low_stock_threshold else 0

    # Update all SKUs for this product
    skus = ProductSKU.query.filter_by(product_id=product.id).all()
    for sku in skus:
        sku.unit = unit
        sku.low_stock_threshold = float(low_stock_threshold) if low_stock_threshold else 0

    db.session.commit()
    flash('Product updated successfully', 'success')
    return redirect(url_for('products.view_product', product_id=product.id))

@products_bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product and all its related data by product ID"""
    try:
        # Get the base SKU to find the product - with org scoping
        base_sku = ProductSKU.query.filter_by(
            inventory_item_id=product_id,
            organization_id=current_user.organization_id
        ).first()

        if not base_sku:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))

        product = base_sku.product

        # Get all SKUs for this product - with org scoping
        skus = ProductSKU.query.filter_by(
            product_id=product.id,
            organization_id=current_user.organization_id
        ).all()

        if not skus:
            flash('Product not found', 'error')
            return redirect(url_for('products.product_list'))

        # Check if any SKU has inventory
        total_inventory = sum((sku.inventory_item.quantity if sku.inventory_item else 0.0) for sku in skus)
        if total_inventory > 0:
            flash('Cannot delete product with remaining inventory', 'error')
            return redirect(url_for('products.view_product', product_id=product_id))

        # Delete history records first
        for sku in skus:
            ProductSKUHistory.query.filter_by(sku_id=sku.id).delete()

        # Delete the SKUs
        ProductSKU.query.filter_by(product_id=product.id).delete()

        # Delete the product and its variants
        from ...models.product import Product, ProductVariant
        ProductVariant.query.filter_by(product_id=product.id).delete()
        Product.query.filter_by(id=product.id).delete()

        db.session.commit()

        flash(f'Product "{product.name}" deleted successfully', 'success')
        return redirect(url_for('products.product_list'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
        return redirect(url_for('products.view_product', product_id=product_id))

# Legacy adjust_sku route removed - use product_inventory routes instead

# API routes moved to product_api.py for better organizationpython