
from app import app, db
from models import Ingredient, Unit, Recipe, Product, ProductInventory, Batch
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

        # Add ingredients
        tallow = Ingredient(name="Tallow", unit="gram", quantity=1000, low_stock_threshold=200, is_perishable=False)
        lavender = Ingredient(name="Lavender EO", unit="gram", quantity=500, low_stock_threshold=100, is_perishable=True)
        db.session.add_all([tallow, lavender])

        # Add product
        product = Product(name="Royal Tallow")
        db.session.add(product)
        db.session.flush()

        # Add inventory
        inv1 = ProductInventory(
            product_id=product.id,
            variant_label="Lavender",
            size_label="4 oz",
            unit="Jar",
            quantity=12,
            expiration_date=datetime.utcnow().date() + timedelta(days=90),
            notes="Demo batch"
        )
        db.session.add(inv1)

        # Add batch
        batch = Batch(
            recipe_name="Royal Tallow - Lavender", 
            product_unit="Jar",
            product_quantity=12,
            label_code="D-001",
            scale=1,
            timestamp=datetime.utcnow(),
            status="completed",
            notes="Demo starter batch"
        )
        db.session.add(batch)
        db.session.flush()
        inv1.batch_id = batch.id

        db.session.commit()
        print("✅ Demo data seeded successfully")

if __name__ == "__main__":
    run_demo()
