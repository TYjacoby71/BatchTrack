
"""
Unit tests for FIFO Service
"""

import unittest
from datetime import datetime, timedelta
from app import create_app, db
from app.models import InventoryItem, InventoryHistory, Organization, User, Role
from app.models.product import ProductSKU, ProductSKUHistory
from app.blueprints.fifo.services import FIFOService
from app.utils.fifo_generator import generate_fifo_code

class TestFIFOService(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Create test organization
        self.org = Organization(name='Test Org')
        db.session.add(self.org)
        db.session.flush()
        
        # Create test user
        self.user = User(
            username='testuser',
            password_hash='test',
            organization_id=self.org.id,
            role_id=1
        )
        db.session.add(self.user)
        db.session.flush()
        
        # Create test ingredient
        self.ingredient = InventoryItem(
            name='Test Ingredient',
            unit='g',
            quantity=100.0,
            cost_per_unit=1.0,
            type='ingredient',
            organization_id=self.org.id
        )
        db.session.add(self.ingredient)
        db.session.flush()
        
        # Create test product
        self.product = InventoryItem(
            name='Test Product',
            unit='piece',
            quantity=50.0,
            cost_per_unit=5.0,
            type='product',
            organization_id=self.org.id
        )
        db.session.add(self.product)
        db.session.flush()
        
        db.session.commit()
    
    def tearDown(self):
        """Clean up after tests"""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_add_fifo_entry(self):
        """Test adding FIFO entry"""
        result = FIFOService.add_fifo_entry(
            inventory_item_id=self.ingredient.id,
            quantity=50.0,
            change_type='manual_addition',
            unit='g',
            notes='Test addition'
        )
        
        self.assertTrue(result)
        
        # Check history was created
        history = InventoryHistory.query.filter_by(
            inventory_item_id=self.ingredient.id
        ).first()
        
        self.assertIsNotNone(history)
        self.assertEqual(history.quantity_change, 50.0)
        self.assertEqual(history.remaining_quantity, 50.0)
        self.assertEqual(history.change_type, 'manual_addition')
    
    def test_calculate_deduction_plan(self):
        """Test deduction plan calculation"""
        # Add some inventory first
        FIFOService.add_fifo_entry(
            inventory_item_id=self.ingredient.id,
            quantity=100.0,
            change_type='manual_addition',
            unit='g'
        )
        
        plan = FIFOService.calculate_deduction_plan(self.ingredient.id, 30.0)
        
        self.assertIsNotNone(plan)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]['quantity_to_deduct'], 30.0)
    
    def test_execute_deduction_plan(self):
        """Test executing deduction plan"""
        # Add inventory
        FIFOService.add_fifo_entry(
            inventory_item_id=self.ingredient.id,
            quantity=100.0,
            change_type='manual_addition',
            unit='g'
        )
        
        # Calculate and execute deduction
        plan = FIFOService.calculate_deduction_plan(self.ingredient.id, 30.0)
        result = FIFOService.execute_deduction_plan(
            self.ingredient.id,
            plan,
            'batch_usage',
            'Test batch usage'
        )
        
        self.assertTrue(result)
        
        # Check remaining quantity
        entries = FIFOService.get_fifo_entries(self.ingredient.id)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].remaining_quantity, 70.0)
    
    def test_recount_fifo(self):
        """Test FIFO recount functionality"""
        # Add initial inventory
        FIFOService.add_fifo_entry(
            inventory_item_id=self.ingredient.id,
            quantity=100.0,
            change_type='manual_addition',
            unit='g'
        )
        
        # Recount to lower amount
        result = FIFOService.recount_fifo(
            self.ingredient.id,
            80.0,
            'Physical count adjustment'
        )
        
        self.assertTrue(result)
        
        # Check updated quantity
        self.ingredient = InventoryItem.query.get(self.ingredient.id)
        self.assertEqual(self.ingredient.quantity, 80.0)
    
    def test_handle_refund_credits(self):
        """Test refund credit handling"""
        # Add inventory and make a sale
        FIFOService.add_fifo_entry(
            inventory_item_id=self.product.id,
            quantity=10.0,
            change_type='manual_addition',
            unit='piece'
        )
        
        plan = FIFOService.calculate_deduction_plan(self.product.id, 5.0)
        FIFOService.execute_deduction_plan(
            self.product.id,
            plan,
            'sold',
            'Test sale'
        )
        
        # Process refund
        result = FIFOService.handle_refund_credits(
            self.product.id,
            2.0,
            'returned',
            'Test refund'
        )
        
        self.assertTrue(result)
        
        # Check inventory was credited back
        self.product = InventoryItem.query.get(self.product.id)
        self.assertEqual(self.product.quantity, 47.0)  # 50 - 5 + 2
    
    def test_reservation_workflow(self):
        """Test complete reservation workflow"""
        # Add inventory
        FIFOService.add_fifo_entry(
            inventory_item_id=self.product.id,
            quantity=20.0,
            change_type='manual_addition',
            unit='piece'
        )
        
        # Make reservation
        plan = FIFOService.calculate_deduction_plan(self.product.id, 3.0)
        FIFOService.execute_deduction_plan(
            self.product.id,
            plan,
            'reserved',
            'Test reservation',
            order_id='ORDER123'
        )
        
        # Convert to sale
        result = FIFOService.convert_reservation_to_sale(
            self.product.id,
            3.0,
            'ORDER123',
            'Convert reservation to sale'
        )
        
        self.assertTrue(result)
        
        # Check final inventory
        self.product = InventoryItem.query.get(self.product.id)
        self.assertEqual(self.product.quantity, 67.0)  # 50 + 20 - 3

if __name__ == '__main__':
    unittest.main()
