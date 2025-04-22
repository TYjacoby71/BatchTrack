
from sqlalchemy import func
from models import db, ProductInventory, Product

def get_product_variant_summary():
    """
    Get a summary of all active product inventory grouped by product, variant, size and unit.
    Returns rows with: product_id, name, variant_label, size_label, unit, total_quantity
    """
    results = db.session.query(
        ProductInventory.product_id,
        Product.name,
        ProductInventory.variant_label,
        ProductInventory.size_label, 
        ProductInventory.unit,
        func.sum(ProductInventory.quantity).label("total_quantity")
    ).join(Product).filter(
        ProductInventory.quantity > 0
    ).group_by(
        ProductInventory.product_id,
        ProductInventory.variant_label,
        ProductInventory.size_label,
        ProductInventory.unit,
        Product.name
    ).all()

    return results
