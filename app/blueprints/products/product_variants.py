import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...services.product_service import ProductService
from ...services.product_variant_route_service import ProductVariantRouteService
from ...utils.permissions import require_permission
from ...utils.settings import is_feature_enabled
from ...utils.unit_utils import get_global_unit_list

logger = logging.getLogger(__name__)


# Create the product variants blueprint
product_variants_bp = Blueprint("product_variants", __name__)


@product_variants_bp.route("/<int:product_id>/variants/new", methods=["POST"])
@login_required
@require_permission("products.manage_variants")
def add_variant(product_id):
    """Quick add new product variant via AJAX"""
    try:
        product = ProductVariantRouteService.get_product_for_variant_flow(
            product_id=product_id,
            organization_id=current_user.organization_id,
        )
        if not product:
            return jsonify({"error": "Product not found"}), 404

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

        existing_variant = ProductVariantRouteService.get_variant_for_product_by_name(
            product_id=product.id,
            variant_name=variant_name,
        )

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

        new_variant, new_sku = (
            ProductVariantRouteService.create_variant_with_optional_bulk_sku(
                product=product,
                variant_name=variant_name,
                description=description,
                organization_id=current_user.organization_id,
                actor_user_id=current_user.id,
                auto_create_bulk_sku=auto_create_bulk_sku,
                unit=unit,
                default_bulk_label=default_bulk_label,
            )
        )

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
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/product_variants.py:163",
            exc_info=True,
        )
        ProductVariantRouteService.rollback_session()
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
    product = ProductVariantRouteService.get_product_for_org(
        product_id=product_id,
        organization_id=current_user.organization_id,
    )

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    variant = ProductVariantRouteService.get_variant_for_product_by_name(
        product_id=product.id,
        variant_name=variant_name,
    )

    if not variant:
        flash("Variant not found", "error")
        return redirect(url_for("products.view_product", product_id=product_id))

    skus = ProductVariantRouteService.list_active_variant_skus_for_org(
        product_id=product.id,
        variant_id=variant.id,
        organization_id=current_user.organization_id,
    )

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

    available_containers = ProductVariantRouteService.list_available_containers_for_org(
        organization_id=current_user.organization_id
    )

    base_variant_id = product.base_variant.id if product.base_variant else variant.id
    base_sku = ProductVariantRouteService.get_bulk_sku_for_variant_org(
        product_id=product.id,
        variant_id=base_variant_id,
        organization_id=current_user.organization_id,
    )

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
        units=get_global_unit_list(),
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
    product = ProductVariantRouteService.get_product_for_org(
        product_id=product_id,
        organization_id=current_user.organization_id,
    )

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    variant = ProductVariantRouteService.get_variant_for_product_by_name(
        product_id=product.id,
        variant_name=variant_name,
    )

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

    existing_sku = ProductVariantRouteService.get_existing_sku_for_variant_size_org(
        product_id=product.id,
        variant_id=variant.id,
        size_label=size_label,
        organization_id=current_user.organization_id,
    )

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
        ProductVariantRouteService.create_sku_for_variant(
            product=product,
            variant=variant,
            size_label=size_label,
            unit=unit,
            low_stock_threshold=low_stock_threshold,
            organization_id=current_user.organization_id,
            actor_user_id=current_user.id,
        )
        flash(f'SKU "{size_label}" created successfully.', "success")
    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/products/product_variants.py:383",
            exc_info=True,
        )
        ProductVariantRouteService.rollback_session()
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
    product = ProductVariantRouteService.get_product_for_org(
        product_id=product_id,
        organization_id=current_user.organization_id,
    )

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    variant = ProductVariantRouteService.get_variant_for_product_by_name(
        product_id=product.id,
        variant_name=variant_name,
    )

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

    existing = ProductVariantRouteService.get_other_variant_by_name(
        product_id=product.id,
        variant_name=name,
        exclude_variant_id=variant.id,
    )

    if existing:
        flash("Another variant with this name already exists for this product", "error")
        return redirect(
            url_for(
                "products.view_variant",
                product_id=product_id,
                variant_name=variant_name,
            )
        )

    ProductVariantRouteService.update_variant(
        variant=variant,
        name=name,
        description=description,
    )
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
    product = ProductVariantRouteService.get_product_for_org(
        product_id=product_id,
        organization_id=current_user.organization_id,
    )

    if not product:
        flash("Product not found", "error")
        return redirect(url_for("products.list_products"))

    variant = ProductVariantRouteService.get_variant_for_product_by_name(
        product_id=product.id,
        variant_name=variant_name,
    )

    if not variant:
        flash("Variant not found", "error")
        return redirect(url_for("products.view_product", product_id=product_id))

    skus = ProductVariantRouteService.list_variant_skus_for_org(
        product_id=product.id,
        variant_id=variant.id,
        organization_id=current_user.organization_id,
    )

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

    ProductVariantRouteService.deactivate_variant_and_skus(
        variant=variant,
        skus=skus,
    )

    remaining_variants = ProductVariantRouteService.count_active_variants_for_product(
        product_id=product.id
    )

    if remaining_variants == 0:
        ProductVariantRouteService.create_default_base_variant(
            product_id=product.id,
            organization_id=current_user.organization_id,
        )
        flash(
            f'Variant "{variant_name}" deleted. Created default "Base" variant.',
            "success",
        )
    else:
        flash(f'Variant "{variant_name}" deleted successfully', "success")

    return redirect(url_for("products.view_product", product_id=product_id))
