
#!/usr/bin/env python3
"""
Script to populate inventory_item_id for existing ProductSKUs
"""

from app import create_app, db
from app.models import ProductSKU, InventoryItem
from flask import current_app

def populate_inventory_items():
    """Create InventoryItem records for existing ProductSKUs and link them"""
    
    app = create_app()
    with app.app_context():
        print("Starting inventory item population...")
        
        # Get all ProductSKUs that don't have inventory_item_id
        skus_without_inventory = ProductSKU.query.filter(
            ProductSKU.inventory_item_id.is_(None)
        ).all()
        
        print(f"Found {len(skus_without_inventory)} SKUs without inventory items")
        
        for sku in skus_without_inventory:
            # Create inventory item for this SKU
            inventory_item = InventoryItem(
                name=f"{sku.product_name} - {sku.variant_name} - {sku.size_label}",
                type='product',
                unit=sku.unit,
                quantity=0.0,  # Start with 0, will be populated from current_quantity if it exists
                organization_id=sku.organization_id,
                created_by=sku.created_by
            )
            
            # If the SKU has current_quantity, use it
            if hasattr(sku, 'current_quantity') and sku.current_quantity is not None:
                inventory_item.quantity = sku.current_quantity
            
            db.session.add(inventory_item)
            db.session.flush()  # Get the ID
            
            # Link the SKU to the inventory item
            sku.inventory_item_id = inventory_item.id
            
            print(f"Created inventory item for SKU: {sku.display_name}")
        
        db.session.commit()
        print(f"Successfully populated {len(skus_without_inventory)} inventory items")

if __name__ == '__main__':
    populate_inventory_items()
