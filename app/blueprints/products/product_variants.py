from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...models import InventoryItem, ProductSKU, db
from ...models.product import Product, ProductVariant
from ...services.product_service import ProductService
from ...utils.permissions import require_permission
from ...utils.settings import is_feature_enabled
from ...utils.unit_utils import get_global_unit_list

# Create the product variants blueprint
product_variants_bp = Blueprint("product_variants", __name__)


@product_variants_bp.route("/<int:product_id>/variants/new", methods=["POST"])
@login_required
@require_permission("products.manage_variants")
def add_variant(product_id):
    """Quick add new product variant via AJAX"""
    try:
        # First try to get the Product record
        product = Product.scoped().filter_by(
            id=product_id, organization_id=current_user.organization_id
        ).first()

        # If no Product record exists, try to find it via ProductSKU and create Product
        if not product:
            # Look for existing SKU with this product_id
            base_sku = ProductSKU.scoped().filter_by(
                id=product_id, organization_id=current_user.organization_id
            ).first()

            if not base_sku:
                return jsonify({"error": "Product not found"}), 404

            # For legacy data, the product_id in the URL might be a SKU ID
            # Try to find or create the actual Product record
            if base_sku.product_id:
                product = db.session.get(Product, base_sku.product_id)

            if not product:
                return jsonify({"error": "Product record not found"}), 404

        # Get variant name from request
        auto_create_bulk_sku = is_feature_enabled("FEATURE_AUTO_BULK_SKU_ON_VARIANT")

        if request.is_json:
            data = request.get_json() or {}
            variant_name = data.get("name")
            description = data.get("description")
            unit_override = data.get("unit") if auto_create_bulk_sku else None
        else:
            variant_name = request.form.get("name")
            description = request.form.get("description")
            unit_override = request.form.get("unit") if auto_create_bulk_sku else None

        if not variant_name or variant_name.strip() == "":
            return jsonify({"error": "Variant name is required"}), 400

        variant_name = variant_name.strip()

        # Check if variant already exists for this product
        existing_variant = ProductVariant.scoped().filter_by(
            product_id=product.id, name=variant_name
        ).first()

        if existing_variant:
            return (
                jsonify(
                    {
                        "error": f'Variant "{variant_name}" already exists for this product'
                    }
                ),
                400,
            )

        unit = ""
        default_bulk_label = "Bulk"
        if auto_create_bulk_sku:
            unit = (unit_override or "").strip() if unit_override else ""
            if not unit:
                return (
                    jsonify(
                        {
                            "error": "Unit is required to create the default Bulk SKU for this variant"
                        }
                    ),
                    400,
                )
            default_bulk_label = ProductService.resolve_bulk_size_label(unit)

        # Create the ProductVariant
        new_variant = ProductVariant(
            product_id=product.id,
            name=variant_name,
            description=description,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
        )
        db.session.add(new_variant)

        new_sku = None
        if auto_create_bulk_sku:
            db.session.flush()  # Ensure new_variant has an ID
            sku_code = ProductService.generate_sku_code(
                product.name, variant_name, default_bulk_label
            )
            sku_name = f"{variant_name} {product.name} ({default_bulk_label})"

            inventory_item = InventoryItem(
                name=f"{product.name} - {variant_name} - {default_bulk_label}",
                type="product",
                unit=unit,
                quantity=0.0,
                organization_id=current_user.organization_id,
                created_by=current_user.id,
            )
            db.session.add(inventory_item)
            db.session.flush()

            new_sku = ProductSKU(
                inventory_item_id=inventory_item.id,
                product_id=product.id,
                variant_id=new_variant.id,
                size_label=default_bulk_label,
                sku_code=sku_code,
                sku=sku_code,
                sku_name=sku_name,
                unit=unit,
                low_stock_threshold=0,
                description=description,
                is_active=True,
                is_product_active=True,
                organization_id=current_user.organization_id,
                created_by=current_user.id,
            )
            db.session.add(new_sku)

        # Commit changes
        db.session.commit()

        response = {
            "success": True,
            "variant": {
                "id": new_variant.id,
                "name": new_variant.name,
                "description": new_variant.description,
            },
        }

        if new_sku:
            response["variant"].update(
                {
                    "sku_id": new_sku.inventory_item_id,
                    "sku": new_sku.sku_code,
                    "unit": new_sku.unit,
                    "size_label": new_sku.size_label,
                }
            )

        return jsonify(response)

    except Exception as e:
        # Rollback any changes if there's an error
        db.session.rollback()
        # Log the full error for debugging
        import traceback

        print(f"Error creating variant: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": f"Failed to create variant: {str(e)}"}), 500


@product_variants_bp.route("/<int:product_id>/variant/<variant_name>")
@login_required
@require_permission("products.view")
def view_variant(product_id, variant_name):
    """View individual product variation details"""
    # Get the product using the new Product model
    from ...models.product import Product, ProductVariant

    product = Product.scoped().filter_by(
        id=product_id, organization_id=current_user.organization_id
    ).first()

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    # Get the variant by name
    variant = ProductVariant.scoped().filter_by(
        product_id=product.id, name=variant_name
    ).first()

    if not variant:
        flash("Variant not found", "error")
        return redirect(url_for("products.view_product", product_id=product_id))

    # Get all SKUs for this product/variant combination
    skus = ProductSKU.scoped().filter_by(
        product_id=product.id,
        variant_id=variant.id,
        is_active=True,
        organization_id=current_user.organization_id,
    ).all()

    # Group SKUs by size_label
    size_groups = {}
    for sku in skus:
        display_size_label = sku.size_label or "Bulk"
        key = f"{display_size_label}_{sku.unit}"

        if key not in size_groups:
            size_groups[key] = {
                "size_label": display_size_label,
                "unit": sku.unit,
                "total_quantity": 0,
                "skus": [],
                "batches": [],  # Add batches for cost calculations
            }

        # Use inventory_item.quantity if available, otherwise use a calculated quantity
        if hasattr(sku, "inventory_item") and sku.inventory_item:
            size_groups[key]["total_quantity"] += sku.inventory_item.quantity
        elif hasattr(sku, "quantity"):
            size_groups[key]["total_quantity"] += sku.quantity
        else:
            size_groups[key]["total_quantity"] += 0
        size_groups[key]["skus"].append(sku)

        # Add batch information for cost calculations
        for batch in sku.batches:
            if batch.final_quantity and batch.final_quantity > 0:
                size_groups[key]["batches"].append(batch)

    # Get available containers for manual stock addition
    available_containers = (
        InventoryItem.scoped().filter_by(type="container", is_archived=False)
        .filter(InventoryItem.quantity > 0)
        .all()
    )

    # Get the base SKU inventory item ID for breadcrumb navigation
    base_sku = ProductSKU.scoped().filter_by(
        product_id=product.id,
        variant_id=product.base_variant.id if product.base_variant else variant.id,
        organization_id=current_user.organization_id,
    ).filter(ProductSKU.size_label.ilike("Bulk%")).first()

    product_breadcrumb_id = (
        base_sku.inventory_item_id
        if base_sku
        else (
            size_groups[list(size_groups.keys())[0]]["skus"][0].inventory_item_id
            if size_groups
            else None
        )
    )

    return render_template(
        "pages/products/view_variation.html",
        product=product,
        product_name=product.name,
        variant_name=variant.name,
        variation=variant,
        variant_description=variant.description,
        size_groups=size_groups,
        available_containers=available_containers,
        get_global_unit_list=get_global_unit_list,
        product_breadcrumb_id=product_breadcrumb_id,
        breadcrumb_items=[
            {"label": "Product Dashboard", "url": url_for("products.list_products")},
            {
                "label": product.name + " Overview",
                "url": url_for("products.view_product", product_id=product.id),
            },
            {"label": variant.name + " Sizes"},
        ],
    )


@product_variants_bp.route(
    "/<int:product_id>/variant/<variant_name>/skus", methods=["POST"]
)
@login_required
@require_permission("products.manage_variants")
def create_sku_for_variant(product_id, variant_name):
    """Create a new SKU for an existing variant."""
    product = Product.scoped().filter_by(
        id=product_id, organization_id=current_user.organization_id
    ).first()

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    variant = ProductVariant.scoped().filter_by(
        product_id=product.id, name=variant_name
    ).first()

    if not variant:
        flash("Variant not found", "error")
        return redirect(url_for("products.view_product", product_id=product_id))

    size_label = (request.form.get("size_label") or "").strip()
    unit = (request.form.get("unit") or "").strip()
    low_stock_threshold = request.form.get("low_stock_threshold")

    if not size_label:
        flash("Size label is required to create a SKU.", "error")
        return redirect(
            url_for(
                "product_variants.view_variant",
                product_id=product_id,
                variant_name=variant_name,
            )
        )

    if not unit:
        flash("Unit is required to create a SKU.", "error")
        return redirect(
            url_for(
                "product_variants.view_variant",
                product_id=product_id,
                variant_name=variant_name,
            )
        )

    existing_sku = ProductSKU.scoped().filter_by(
        product_id=product.id,
        variant_id=variant.id,
        size_label=size_label,
        organization_id=current_user.organization_id,
    ).first()

    if existing_sku:
        flash(f'SKU with size "{size_label}" already exists for this variant.', "error")
        return redirect(
            url_for(
                "product_variants.view_variant",
                product_id=product_id,
                variant_name=variant_name,
            )
        )

    try:
        inventory_item = InventoryItem(
            name=f"{product.name} - {variant.name} - {size_label}",
            type="product",
            unit=unit,
            quantity=0.0,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
        )
        db.session.add(inventory_item)
        db.session.flush()

        sku_code = ProductService.generate_sku_code(
            product.name, variant.name, size_label
        )

        new_sku = ProductSKU(
            inventory_item_id=inventory_item.id,
            product_id=product.id,
            variant_id=variant.id,
            size_label=size_label,
            sku_code=sku_code,
            sku=sku_code,
            sku_name=f"{variant.name} {product.name} ({size_label})",
            unit=unit,
            low_stock_threshold=(
                float(low_stock_threshold) if low_stock_threshold else 0
            ),
            organization_id=current_user.organization_id,
            created_by=current_user.id,
            is_active=True,
            is_product_active=True,
        )
        db.session.add(new_sku)
        db.session.commit()

        flash(f'SKU "{size_label}" created successfully.', "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Failed to create SKU: {str(e)}", "error")

    return redirect(
        url_for(
            "product_variants.view_variant",
            product_id=product_id,
            variant_name=variant_name,
        )
    )


@product_variants_bp.route(
    "/<int:product_id>/variant/<variant_name>/edit", methods=["POST"]
)
@login_required
@require_permission("products.manage_variants")
def edit_variant(product_id, variant_name):
    """Edit product variation details"""
    from ...models.product import Product, ProductVariant

    # Get the product using the new Product model
    product = Product.scoped().filter_by(
        id=product_id, organization_id=current_user.organization_id
    ).first()

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    # Get the variant
    variant = ProductVariant.scoped().filter_by(
        product_id=product.id, name=variant_name
    ).first()

    if not variant:
        flash("Variant not found", "error")
        return redirect(url_for("products.view_product", product_id=product_id))

    name = request.form.get("name")
    description = request.form.get("description")

    if not name:
        flash("Variant name is required", "error")
        return redirect(
            url_for(
                "products.view_variant",
                product_id=product_id,
                variant_name=variant_name,
            )
        )

    # Check if another variant has this name for the same product
    existing = ProductVariant.scoped().filter(
        ProductVariant.product_id == product.id,
        ProductVariant.name == name,
        ProductVariant.id != variant.id,
    ).first()

    if existing:
        flash("Another variant with this name already exists for this product", "error")
        return redirect(
            url_for(
                "products.view_variant",
                product_id=product_id,
                variant_name=variant_name,
            )
        )

    # Update the variant
    variant.name = name
    variant.description = description

    db.session.commit()
    flash("Variant updated successfully", "success")

    return redirect(
        url_for("products.view_variant", product_id=product_id, variant_name=name)
    )


@product_variants_bp.route(
    "/<int:product_id>/variant/<variant_name>/delete", methods=["POST"]
)
@login_required
@require_permission("products.manage_variants")
def delete_variant(product_id, variant_name):
    """Delete a product variant and all its SKUs"""
    from ...models.product import Product, ProductVariant

    # Get the product using the new Product model
    product = Product.scoped().filter_by(
        id=product_id, organization_id=current_user.organization_id
    ).first()

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    # Get the variant
    variant = ProductVariant.scoped().filter_by(
        product_id=product.id, name=variant_name
    ).first()

    if not variant:
        flash("Variant not found", "error")
        return redirect(url_for("products.view_product", product_id=product_id))

    # Get all SKUs for this variant
    skus = ProductSKU.scoped().filter_by(
        product_id=product.id,
        variant_id=variant.id,
        organization_id=current_user.organization_id,
    ).all()

    if not skus:
        flash("Variant not found", "error")
        return redirect(url_for("products.view_product", product_id=product_id))

    # Check if any SKUs have inventory
    has_inventory = any(sku.inventory_item.quantity > 0 for sku in skus)
    if has_inventory:
        flash("Cannot delete variant with existing inventory", "error")
        return redirect(
            url_for(
                "products.view_variant",
                product_id=product_id,
                variant_name=variant_name,
            )
        )

    # Delete the variant and its SKUs
    variant.is_active = False
    for sku in skus:
        sku.is_active = False

    db.session.commit()

    # Check if this was the last variant for the product
    remaining_variants = ProductVariant.scoped().filter_by(
        product_id=product.id, is_active=True
    ).count()

    if remaining_variants == 0:
        # Create a Base variant
        base_variant = ProductVariant(
            product_id=product.id,
            name="Base",
            description="Default base variant",
            organization_id=current_user.organization_id,
        )
        db.session.add(base_variant)
        db.session.commit()
        flash(
            f'Variant "{variant_name}" deleted. Created default "Base" variant.',
            "success",
        )
    else:
        flash(f'Variant "{variant_name}" deleted successfully', "success")

    return redirect(url_for("products.view_product", product_id=product_id))
