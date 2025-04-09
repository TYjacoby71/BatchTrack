
from app import app, db
from models import InventoryUnit

with app.app_context():
    # Define base unit values for volume (in ml) and weight (in g)
    volume_units = {
        'ml': 1,
        'l': 1000,
        'tsp': 5,
        'tbsp': 15,
        'fl oz': 29.5735,
        'cup': 240,
        'pint': 473.176,
        'quart': 946.353,
        'gallon': 3785.41
    }

    weight_units = {
        'g': 1,
        'kg': 1000,
        'oz': 28.3495,
        'lb': 453.592
    }

    for name, base_eq in volume_units.items():
        if not InventoryUnit.query.filter_by(name=name).first():
            db.session.add(InventoryUnit(
                name=name,
                type='volume',
                base_equivalent=base_eq,
                aliases='',
                density_required=False
            ))

    for name, base_eq in weight_units.items():
        if not InventoryUnit.query.filter_by(name=name).first():
            db.session.add(InventoryUnit(
                name=name,
                type='weight',
                base_equivalent=base_eq,
                aliases='',
                density_required=False
            ))

    db.session.commit()
    print("Seeded volume and weight units.")
