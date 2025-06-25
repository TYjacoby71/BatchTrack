from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from ...models import db, Product, ProductEvent, InventoryItem, ProductVariation
from datetime import datetime
from werkzeug.utils import secure_filename
import os
from ...blueprints.fifo.services import deduct_fifo
from ...utils.unit_utils import get_global_unit_list

from . import products_bp

@products_bp.route('/<int:product_id>/variant/<int:variation_id>')
@login_required
def view_variant(product_id, variation_id):
    product = Product.query.get_or_404(product_id)
    variation = ProductVariation.query.filter_by(id=variation_id, product_id=product_id).first_or_404()
    return render_template('products/view_variation.html', product=product, variation=variation)

@products_bp.route("/<int:product_id>/deduct", methods=["POST"])
@login_required
def deduct_product(product_id):
    from ..services.product_service import ProductService

    variant = request.form.get("variant", "Base")
    size_label = request.form.get("size_label", "Bulk")
    unit = request.form.get("unit")
    reason = request.form.get("reason", "manual_deduction")
    notes = request.form.get("notes", "")

    try:
        quantity = float(request.form.get("quantity", 0))
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        success = ProductService.process_inventory_adjustment(
            product_id=product_id,
            variant=variant,
            size_label=size_label,
            adjustment_type=reason,
            quantity=quantity,
            notes=notes
        )

        if success:
            flash(f"Deducted {quantity} {unit} from {variant} - {size_label} using FIFO", "success")
        else:
            flash("Not enough stock to fulfill request", "danger")

    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash("Error processing deduction request", "danger")

    return redirect(url_for('products.view_product', product_id=product_id))