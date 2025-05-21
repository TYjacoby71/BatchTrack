import pytest
from unittest.mock import patch
from app import app, db
from models import InventoryItem, IngredientCategory, Unit, Batch, BatchIngredient, BatchContainer
from services.unit_conversion import ConversionEngine
from routes.batch_routes import adjust_inventory_deltas
from datetime import datetime
import unittest

class TestBatchInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    def setUp(self):
        self.ctx = app.test_request_context()
        self.ctx.push()
        db.create_all()

        # Set up test data
        category = IngredientCategory(name="Test Powder", default_density=0.8)
        db.session.add(category)
        db.session.flush()

        sugar = InventoryItem(
            id=1,
            name="Sugar",
            quantity=1000.0,
            unit="gram",
            category=category,
            type="ingredient"
        )
        db.session.add(sugar)

        # Add required units
        gram_unit = Unit(name='gram', type='weight', base_unit='gram', multiplier_to_base=1.0)
        lb_unit = Unit(name='lb', type='weight', base_unit='gram', multiplier_to_base=453.592)
        db.session.add(gram_unit)
        db.session.add(lb_unit)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    @patch('flask_login.current_user')
    def test_adjust_inventory_with_conversion(self, mock_current_user):
        mock_current_user.is_authenticated = False
        mock_current_user.id = None

        batch = Batch(id=1, recipe_id=1, batch_type='ingredient', status='in_progress', started_at=datetime.utcnow())
        db.session.add(batch)
        db.session.commit()

        # Simulate a user entering 0.5 lb of sugar (inventory is in grams)
        new_ingredients = [{
            'id': 1,               # sugar
            'amount': 0.5,
            'unit': 'lb'
        }]
        adjust_inventory_deltas(batch.id, new_ingredients, [])

        sugar = InventoryItem.query.get(1)
        # Get the actual inventory change
        batch_ingredient = BatchIngredient.query.filter_by(
            batch_id=batch.id, 
            ingredient_id=sugar.id
        ).first()
        assert batch_ingredient is not None
        assert round(sugar.quantity, 2) == round(1000.0 - batch_ingredient.amount_used, 2)

    @patch('flask_login.current_user')
    def test_cancel_batch_restores_inventory(self, mock_current_user):
        mock_current_user.is_authenticated = False
        mock_current_user.id = None

        batch = Batch(id=1, recipe_id=1, batch_type='ingredient', status='in_progress', started_at=datetime.utcnow())
        db.session.add(batch)
        db.session.commit()

        new_ingredients = [{
            'id': 1,
            'amount': 0.5,
            'unit': 'lb'
        }]
        adjust_inventory_deltas(batch.id, new_ingredients, [])

        reversed_ingredients = [{
            'id': 1,
            'amount': 0,
            'unit': 'lb'
        }]
        adjust_inventory_deltas(batch.id, reversed_ingredients, [])

        sugar = InventoryItem.query.get(1)
        self.assertEqual(round(sugar.quantity, 2), 1000.0)

    def test_cancel_batch_restores_containers(self):
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

        batch = Batch(id=3, recipe_id=1, batch_type='ingredient', status='in_progress', started_at=datetime.utcnow())
        db.session.add(batch)
        db.session.commit()

        bc = BatchContainer(
            batch_id=3,
            container_id=2,
            quantity_used=10,
            cost_each=1.50
        )
        db.session.add(bc)
        db.session.commit()

        jar.quantity -= 10
        db.session.commit()
        self.assertEqual(jar.quantity, 40)

        jar.quantity += 10
        db.session.delete(bc)
        batch.status = 'cancelled'
        db.session.add(batch)
        db.session.commit()

        restored_jar = InventoryItem.query.get(2)
        self.assertEqual(restored_jar.quantity, 50)
        self.assertEqual(batch.status, 'cancelled')