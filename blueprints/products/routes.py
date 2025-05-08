
from flask import Blueprint, render_template
from flask_login import login_required
from models import ProductInventory

products_bp = Blueprint('products', __name__)

@products_bp.route("/batches/<int:product_id>/variant/<variant>/size/<size>/unit/<unit>")
@login_required
def view_batches_by_variant(product_id, variant, size, unit):
    """View FIFO-ordered batches for a specific product variant"""
    batches = ProductInventory.query.filter_by(
        product_id=product_id,
        variant_label=variant,
        size_label=size,
        unit=unit
    ).filter(ProductInventory.quantity > 0).order_by(ProductInventory.timestamp.asc()).all()

    return render_template(
        "batches/by_variant.html",
        batches=batches,
        variant=variant,
        size=size,
        unit=unit
    )
