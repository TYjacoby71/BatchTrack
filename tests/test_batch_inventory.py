import pytest
from app import app, db
from models import InventoryItem, IngredientCategory, Unit, Batch, BatchIngredient, BatchContainer
from services.unit_conversion import ConversionEngine
from routes.batch_routes import adjust_inventory_deltas
from datetime import datetime
import unittest

class TestBatchInventory(unittest.TestCase):
    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()

            # Clear any existing categories
            IngredientCategory.query.delete()
            db.session.commit()

            category = IngredientCategory(name="Test Powder", default_density=0.8)
            db.session.add(category)
            db.session.flush()

            sugar = InventoryItem(
                id=1,
                name="Sugar",
                quantity=1000.0,  # in grams
                unit="gram",
                category=category,
                type="ingredient"
            )
            db.session.add(sugar)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.drop_all()


    def test_adjust_inventory_with_conversion(self):
        with app.app_context():
            batch = Batch(id=1, recipe_id=1, batch_type='ingredient', status='in_progress', started_at=datetime.utcnow())
            db.session.add(batch)
            db.session.commit()

            # Add required units
            gram_unit = Unit(name='gram', type='weight', base_unit='gram', multiplier_to_base=1.0)
            lb_unit = Unit(name='lb', type='weight', base_unit='gram', multiplier_to_base=453.592)
            db.session.add(gram_unit)
            db.session.add(lb_unit)
            db.session.commit()

            # Simulate a user entering 0.5 lb of sugar (inventory is in grams)
            new_ingredients = [{
                'id': 1,               # sugar
                'amount': 0.5,        # 0.5 lb
                'unit': 'lb'
            }]
            adjust_inventory_deltas(batch.id, new_ingredients, [])

            sugar = InventoryItem.query.get(1)
            result = ConversionEngine.convert_units(0.5, 'lb', 'gram')
            assert round(sugar.quantity, 2) == round(1000.0 - result['converted_value'], 2)


    def test_cancel_batch_restores_containers(self):
        with app.app_context():
            # Set up a container in inventory
            container_category = IngredientCategory(name="Container", default_density=1.0)
            db.session.add(container_category)

            jar = InventoryItem(
                id=2,
                name="Glass Jar",
                quantity=50,
                unit="count",
                type="container",
                category=container_category
            )
            db.session.add(jar)
            db.session.commit()

            # Create batch and add container usage
            batch = Batch(id=3, recipe_id=1, batch_type='ingredient', status='in_progress', started_at=datetime.utcnow())
            db.session.add(batch)
            db.session.commit()

            # Add container usage record
            bc = BatchContainer(
                batch_id=3,
                container_id=2,
                quantity_used=10,
                cost_each=1.50
            )
            db.session.add(bc)
            db.session.commit()

            # Pre-deduct container inventory
            jar.quantity -= 10
            db.session.commit()
            self.assertEqual(jar.quantity, 40)  # Verify deduction

            # Cancel batch and restore container
            jar.quantity += 10
            db.session.delete(bc)
            batch.status = 'cancelled'
            db.session.add(batch)
            db.session.commit()

            # Verify restoration
            restored_jar = InventoryItem.query.get(2)
            self.assertEqual(restored_jar.quantity, 50)
            self.assertEqual(batch.status, 'cancelled')

            new_containers = []
            adjust_inventory_deltas(batch.id, [], new_containers)


    def test_cancel_batch_restores_inventory(self):
        with app.app_context():
            batch = Batch(id=1, recipe_id=1, batch_type='ingredient', status='in_progress', started_at=datetime.utcnow())
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
            self.assertEqual(round(sugar.quantity, 2), 1000.0)  # Should be back to original amount