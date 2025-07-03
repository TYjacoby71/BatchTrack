
#!/usr/bin/env python3
"""
Migration script to populate Product and ProductVariant tables from existing ProductSKU data
"""

from app import create_app, db
from app.models import ProductSKU, Product, ProductVariant
from sqlalchemy import text

def migrate_to_product_model():
    """Migrate existing ProductSKU data to Product and ProductVariant structure"""
    
    app = create_app()
    with app.app_context():
        print("Starting migration to Product/ProductVariant structure...")
        
        # Get all distinct products from ProductSKU
        distinct_products = db.session.query(
            ProductSKU.product_name,
            ProductSKU.unit,
            ProductSKU.organization_id,
            ProductSKU.created_by,
            ProductSKU.low_stock_threshold
        ).distinct(ProductSKU.product_name, ProductSKU.organization_id).all()
        
        product_count = 0
        variant_count = 0
        
        for product_data in distinct_products:
            product_name, base_unit, org_id, created_by, threshold = product_data
            
            # Create or get Product
            product = Product.query.filter_by(
                name=product_name,
                organization_id=org_id
            ).first()
            
            if not product:
                product = Product(
                    name=product_name,
                    base_unit=base_unit,
                    organization_id=org_id,
                    created_by=created_by,
                    low_stock_threshold=threshold or 10.0
                )
                db.session.add(product)
                db.session.flush()
                product_count += 1
                print(f"Created product: {product_name}")
            
            # Get all variants for this product
            variants = db.session.query(
                ProductSKU.variant_name
            ).filter_by(
                product_name=product_name,
                organization_id=org_id
            ).distinct().all()
            
            for variant_data in variants:
                variant_name = variant_data[0]
                
                # Create or get ProductVariant
                variant = ProductVariant.query.filter_by(
                    product_id=product.id,
                    name=variant_name
                ).first()
                
                if not variant:
                    variant = ProductVariant(
                        product_id=product.id,
                        name=variant_name,
                        organization_id=org_id
                    )
                    db.session.add(variant)
                    db.session.flush()
                    variant_count += 1
                    print(f"Created variant: {product_name} - {variant_name}")
                
                # Update all SKUs for this product/variant combination
                skus = ProductSKU.query.filter_by(
                    product_name=product_name,
                    variant_name=variant_name,
                    organization_id=org_id
                ).all()
                
                for sku in skus:
                    sku.product_id = product.id
                    sku.variant_id = variant.id
                    # Keep legacy fields for now
        
        db.session.commit()
        print(f"Migration complete! Created {product_count} products and {variant_count} variants.")
        print("Legacy product_name and variant_name fields retained for compatibility.")

if __name__ == '__main__':
    migrate_to_product_model()
