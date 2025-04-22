
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Unit, Product, ProductInventory, Ingredient, Batch
from datetime import datetime, timedelta

def run_demo():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Add units
        units = [
            Unit(name="gram", type="weight", base_unit="gram", multiplier_to_base=1),
            Unit(name="kg", type="weight", base_unit="gram", multiplier_to_base=1000),
            Unit(name="jar", type="product", base_unit="unit", multiplier_to_base=1)
        ]
        db.session.add_all(units)
        db.session.commit()

        # Add ingredients
        ingredients = [
            Ingredient(name="Tallow", unit="gram", quantity=1000, low_stock_threshold=200),
            Ingredient(name="Lavender EO", unit="gram", quantity=250, low_stock_threshold=50),
            Ingredient(name="Coconut Oil", unit="gram", quantity=500, low_stock_threshold=100)
        ]
        db.session.add_all(ingredients)
        db.session.commit()

        # Add products
        product = Product(name="Royal Tallow Soap", default_unit="jar", low_stock_threshold=5)
        db.session.add(product)
        db.session.commit()

        # Add inventory
        inventory = ProductInventory(
            product_id=product.id,
            variant="Lavender",
            unit="jar",
            quantity=20,
            expiration_date=datetime.utcnow().date() + timedelta(days=90),
            notes="Demo batch"
        )
        db.session.add(inventory)

        # Add batch
        batch = Batch(
            recipe_name="Royal Tallow - Lavender",
            status="completed",
            label_code="DEMO-001",
            scale=1.0,
            notes="Initial demo batch"
        )
        db.session.add(batch)
        db.session.commit()

        print("✅ Demo data loaded successfully")

if __name__ == "__main__":
    run_demo()
