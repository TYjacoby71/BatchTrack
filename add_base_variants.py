
from app import db
from app.models import Product, ProductVariation

def add_base_variants():
    """Add Base variant to products that don't have one"""
    products = Product.query.all()
    
    for product in products:
        # Check if product already has a Base variant
        base_variant = ProductVariation.query.filter_by(
            product_id=product.id,
            name='Base'
        ).first()
        
        if not base_variant:
            base_variant = ProductVariation(
                product_id=product.id,
                name='Base',
                description='Default base variant'
            )
            db.session.add(base_variant)
            print(f"Added Base variant to product: {product.name}")
    
    db.session.commit()
    print("Base variant migration complete!")

if __name__ == "__main__":
    add_base_variants()
