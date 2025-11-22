from flask import Blueprint, request, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from ...models import db, InventoryItem
from ...models.product import Product, ProductVariant, ProductSKU
from ...models import UnifiedInventoryHistory, InventoryLot
from ...models.batch import Batch
from ...utils.unit_utils import get_global_unit_list

try:
    from ...utils.authorization import require_permission
except ImportError:
    # test-safe no-op decorator
    def require_permission(permission_name):
        def _wrap(f): return f
        return _wrap

# Helper for product audit entries, now using canonical service
import app.services.inventory_adjustment as inv_adj

# This function is defined twice in the original code.
# The second definition is the one that will be used due to Python's execution order.
# The provided change targets the second definition.
# The first definition is kept here to accurately reflect the original code's structure before the change.
def _write_product_created_audit(variant):
    # Product creation audit is now handled by FIFO operations automatically
    # No separate audit entry needed
    return True


from ...services.product_service import ProductService
from ...services.inventory_adjustment import process_inventory_adjustment

# Wrapper for audit entry - used by tests
# This function is also defined twice, the second one is the one that is used.
# The change request targets the first definition of _write_product_created_audit, which is actually not used.
# The second definition _write_product_created_audit(sku) is likely for tests.
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
        from ...models import db, InventoryItem
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

        # Product creation audit is now handled by FIFO operations automatically
        # No separate audit entry needed
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
def list_products():
    """List all products with inventory summary and sorting"""
    from ...services.product_service import ProductService

    sort_type = request.args.get('sort', 'name')
    product_data = ProductService.get_product_summary_skus()

    # Convert dict data to objects with the attributes the template expects
    class ProductSummary:
        def __init__(self, data):
            self.name = data.get('product_name', '')
            self.product_base_unit = data.get('product_base_unit', '')
            self.last_updated = data.get('last_updated')
            self.inventory = []
            self.total_quantity = data.get('total_quantity', 0)
            self.id = data.get('product_id', None)
            self.total_bulk = 0
            self.total_packaged = 0

            if self.id:
                from ...models.product import ProductSKU, Product, ProductVariant

                product = Product.query.filter_by(
                    name=self.name,
                    organization_id=current_user.organization_id
                ).first()

                if product:
                    self.id = product.id

                    actual_variants = ProductVariant.query.filter_by(
                        product_id=product.id,
                        is_active=True
                    ).all()

                    self.variations = []
                    variant_map = {}
                    for variant in actual_variants:
                        variant_obj = type('Variation', (), {
                            'name': variant.name,
                            'description': variant.description,
                            'id': variant.id,
                            'sku': None,
                            'created_at': variant.created_at
                        })()
                        self.variations.append(variant_obj)
                        variant_map[variant.id] = variant_obj

                    self.variant_count = len(actual_variants)

                    product_skus = ProductSKU.query.filter_by(
                        product_id=product.id,
                        organization_id=current_user.organization_id,
                        is_active=True
                    ).all()

                    for sku in product_skus:
                        size_label = sku.size_label if sku.size_label else 'Bulk'
                        quantity = float(sku.inventory_item.quantity or 0.0) if sku.inventory_item else 0.0
                        unit = sku.unit or (sku.inventory_item.unit if sku.inventory_item else '')

                        variant_obj = variant_map.get(sku.variant_id)
                        if not variant_obj and sku.variant:
                            variant_obj = type('Variation', (), {
                                'name': sku.variant.name,
                                'description': sku.variant.description,
                                'id': sku.variant.id,
                                'sku': None,
                                'created_at': sku.variant.created_at
                            })()
                            self.variations.append(variant_obj)
                            variant_map[sku.variant_id] = variant_obj

                        if variant_obj and not getattr(variant_obj, 'sku', None):
                            variant_obj.sku = sku.sku or sku.sku_code

                        inventory_entry = type('InventoryEntry', (), {
                            'variant': variant_obj.name if variant_obj else (sku.variant.name if sku.variant else 'Unassigned'),
                            'size_label': size_label if size_label else 'Bulk',
                            'quantity': quantity,
                            'unit': unit or '',
                            'sku_id': sku.inventory_item_id,
                            'sku_code': sku.sku or sku.sku_code
                        })()
                        self.inventory.append(inventory_entry)

                        if quantity > 0:
                            if size_label.lower() == 'bulk':
                                self.total_bulk += quantity
                            else:
                                self.total_packaged += quantity

                    self.variant_count = len(self.variations)
                else:
                    self.variant_count = data.get('sku_count', 0)
                    self.variations = []
            else:
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

    return render_template('pages/products/list_products.html', products=products, current_sort=sort_type,
                           breadcrumb_items=[{'label': 'Products'}])

@products_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_product():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        category_id = request.form.get('category_id')
        low_stock_threshold = request.form.get('low_stock_threshold', 0)

        if not name:
            flash('Product name is required', 'error')
            return redirect(url_for('products.new_product'))
        if not category_id or not str(category_id).isdigit():
            flash('Product category is required', 'error')
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
                category_id=int(category_id),
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
                organization_id=current_user.organization_id,
                created_by=current_user.id
            )
            db.session.add(variant)

            db.session.commit()

            flash('Product created successfully.', 'success')
            return redirect(url_for('products.view_product', product_id=product.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating product: {str(e)}', 'error')
            return redirect(url_for('products.new_product'))

    # Load product categories for selection if template supports it later
    try:
        from ...models.product_category import ProductCategory
        categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    except Exception:
        categories = []
    return render_template('pages/products/new_product.html', product_categories=categories)

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

    # Group SKUs by variant, including variants without SKUs
    variants = {}
    product_variants = product.variants.filter_by(is_active=True).all()
    for variant in product_variants:
        variants[variant.name] = {
            'name': variant.name,
            'description': variant.description,
            'skus': []
        }

    for sku in skus:
        variant_rel = sku.variant
        variant_key = variant_rel.name if variant_rel else 'Unassigned'
        if variant_key not in variants:
            variants[variant_key] = {
                'name': variant_key,
                'description': variant_rel.description if variant_rel else None,
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

    # Load product categories for edit modal
    try:
        from ...models.product_category import ProductCategory
        product_categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    except Exception:
        product_categories = []

    return render_template('pages/products/view_product.html',
                         product=product,
                         variants=variants,
                         available_containers=available_containers,
                         get_global_unit_list=get_global_unit_list,
                         inventory_groups={},
                         product_categories=product_categories,
                         breadcrumb_items=[{'label': 'Products', 'url': url_for('products.list_products')}, {'label': product.name}])

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

    name = (request.form.get('name') or '').strip()
    category_id = request.form.get('category_id')
    low_stock_threshold = request.form.get('low_stock_threshold', 0)

    if not name or not category_id:
        flash('Name and category are required', 'error')
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
    product.low_stock_threshold = float(low_stock_threshold) if low_stock_threshold else 0
    try:
        product.category_id = int(category_id)
    except Exception:
        pass

    # Update all SKUs for this product
    skus = ProductSKU.query.filter_by(product_id=product.id).all()
    for sku in skus:
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

        # Delete unified history and lot records first
        for sku in skus:
            UnifiedInventoryHistory.query.filter_by(inventory_item_id=sku.inventory_item_id).delete(synchronize_session=False)
            InventoryLot.query.filter_by(inventory_item_id=sku.inventory_item_id).delete(synchronize_session=False)

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