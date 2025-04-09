
from app import app
from models import db, InventoryUnit, ProductUnit

with app.app_context():
    db.create_all()

    # Seed default units if not present
    if not InventoryUnit.query.first():
        defaults = [
            InventoryUnit(name="ml", type="volume", base_equivalent=1.0, aliases="milliliter", density_required=False),
            InventoryUnit(name="l", type="volume", base_equivalent=1000.0, aliases="liter", density_required=False),
            InventoryUnit(name="g", type="weight", base_equivalent=1.0, aliases="gram", density_required=False),
            InventoryUnit(name="kg", type="weight", base_equivalent=1000.0, aliases="kilogram", density_required=False),
            InventoryUnit(name="count", type="count", base_equivalent=1.0, aliases="each", density_required=False),
        ]
        db.session.add_all(defaults)

    if not ProductUnit.query.first():
        db.session.add(ProductUnit(name="jar"))
        db.session.add(ProductUnit(name="bar"))

    db.session.commit()
    print("Database initialized and seeded.")
