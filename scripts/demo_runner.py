import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Unit, Product, ProductInventory, InventoryItem, Batch, ProductVariation
from datetime import datetime, timedelta

def run_demo():
    with app.app_context():
        # Reset database
        db.drop_all()
        db.create_all()

        # Add base units
        gram = Unit(name="gram", type="weight", base_unit="gram", multiplier_to_base=1)
        jar = Unit(name="Jar", type="count", base_unit="unit", multiplier_to_base=1)
        db.session.add_all([gram, jar])

        # Add ingredients as inventory items
        tallow = InventoryItem(name="Tallow", unit="gram", quantity=1000, low_stock_threshold=200, is_perishable=False)
        lavender = InventoryItem(name="Lavender EO", unit="gram", quantity=500, low_stock_threshold=100, is_perishable=True)
        db.session.add_all([tallow, lavender])

        # Add product
        product = Product(name="Royal Tallow", default_unit="Jar", low_stock_threshold=5)
        db.session.add(product)
        db.session.flush()

        # Add product variation
        variation = ProductVariation(product_id=product.id, name="Lavender", sku="RT-LAV-001")
        db.session.add(variation)

        # Add inventory
        inv1 = ProductInventory(
            product_id=product.id,
            variant="Lavender",
            unit="Jar",
            quantity=12,
            expiration_date=datetime.utcnow().date() + timedelta(days=90),
            notes="Demo batch"
        )
        db.session.add(inv1)

        # Add batch
        batch = Batch(
            recipe_name="Royal Tallow - Lavender", 
            status="completed",
            product_unit="Jar",
            product_quantity=12,
            label_code="D-001",
            scale=1,
            timestamp=datetime.utcnow(),
            notes="Demo starter batch"
        )
        db.session.add(batch)
        db.session.flush()
        inv1.batch_id = batch.id

        db.session.commit()
        print("✅ Demo data seeded successfully")

if __name__ == "__main__":
    run_demo()