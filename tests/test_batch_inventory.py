
import pytest
from app import app, db
from models import InventoryItem, IngredientCategory, Unit, Batch, BatchIngredient
from services.unit_conversion import UnitConversionService
from routes.batches import adjust_inventory_deltas
from datetime import datetime

@pytest.fixture
def setup_inventory():
    with app.app_context():
        db.create_all()

        category = IngredientCategory(name="Powder", default_density=0.8)
        db.session.add(category)

        sugar = InventoryItem(
            id=1,
            name="Sugar",
            quantity=1000.0,  # in grams
            unit="gram",
            category=category,
            type="ingredient"
        )
        db.session.add(sugar)

        # Units already seeded (e.g., gram, lb)
        db.session.commit()
        yield
        db.drop_all()


def test_adjust_inventory_with_conversion(setup_inventory):
    with app.app_context():
        batch = Batch(id=1, recipe_id=1, status='in_progress', started_at=datetime.utcnow())
        db.session.add(batch)
        db.session.commit()

        # Simulate a user entering 0.5 lb of sugar (inventory is in grams)
        new_ingredients = [{
            'id': 1,               # sugar
            'amount': 0.5,        # 0.5 lb
            'unit': 'lb'
        }]

        new_containers = []
        adjust_inventory_deltas(batch.id, new_ingredients, new_containers)

        sugar = InventoryItem.query.get(1)
        converted = UnitConversionService.convert(0.5, 'lb', 'gram')
        assert round(sugar.quantity, 2) == round(1000.0 - converted, 2)


def test_cancel_batch_restores_inventory(setup_inventory):
    with app.app_context():
        batch = Batch(id=1, recipe_id=1, status='in_progress', started_at=datetime.utcnow())
        db.session.add(batch)
        db.session.commit()

        # First deduct inventory
        new_ingredients = [{
            'id': 1,
            'amount': 0.5,
            'unit': 'lb'
        }]
        adjust_inventory_deltas(batch.id, new_ingredients, [])
        
        # Then simulate cancelling by reversing the delta
        reversed_ingredients = [{
            'id': 1,
            'amount': 0,  # Setting to 0 should restore the full amount
            'unit': 'lb'
        }]
        adjust_inventory_deltas(batch.id, reversed_ingredients, [])

        sugar = InventoryItem.query.get(1)
        assert round(sugar.quantity, 2) == 1000.0  # Should be back to original amount
