import pytest
from unittest.mock import patch, MagicMock
from flask_login import login_user
from app import create_app
from app.extensions import db
from app.models.models import User, Organization, InventoryItem
from app.models.category import IngredientCategory


class TestInventoryRoutesCanonicalService:
    """Verify inventory routes use canonical inventory adjustment service"""

    def test_adjust_inventory_initial_stock_calls_canonical_service(self, app, client):
        """Test that initial stock adjustment uses canonical inventory service"""
        
        with app.app_context():
            # Create all tables
            db.create_all()
            
            # Create subscription tier first (needed for middleware)
            from app.models.subscription_tier import SubscriptionTier
            test_tier = SubscriptionTier(
                name='Test Tier',
                key='test_tier',
                is_billing_exempt=True,  # Bypass billing checks
                billing_provider='exempt',
                user_limit=10
            )
            db.session.add(test_tier)
            db.session.flush()
            
            # Create a real test organization with subscription tier
            test_org = Organization(
                name='Test Organization',
                subscription_tier_id=test_tier.id,
                billing_status='active'  # Ensure billing is active
            )
            db.session.add(test_org)
            db.session.flush()  # Get the ID
            
            # Create a real test user
            test_user = User(
                username='testuser_inventory',
                email='test_inventory@example.com', 
                organization_id=test_org.id,
                user_type='customer',
                is_active=True,
                password_hash='test_hash'
            )
            db.session.add(test_user)
            db.session.flush()
            
            # Create a test ingredient category
            test_category = IngredientCategory(
                name='Test Category',
                organization_id=test_org.id
            )
            db.session.add(test_category)
            db.session.flush()
            
            # Create a real inventory item with no history
            test_item = InventoryItem(
                name='Test Ingredient',
                type='ingredient',
                unit='g',
                cost_per_unit=2.5,
                is_perishable=False,
                organization_id=test_org.id,
                category_id=test_category.id,
                quantity=0.0  # Start with zero quantity
            )
            db.session.add(test_item)
            db.session.commit()
            
            # Patch the canonical service to track calls
            with patch('app.blueprints.inventory.routes.process_inventory_adjustment') as mock_process:
                mock_process.return_value = (True, "Success")
                
                # Log in the test user properly
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(test_user.id)
                    sess['_fresh'] = True
                
                # Make POST request to adjust inventory
                response = client.post(f'/inventory/adjust/{test_item.id}', data={
                    'adjustment_type': 'restock',
                    'quantity': '100.0',
                    'input_unit': 'g',
                    'notes': 'Initial stock',
                    'cost_entry_type': 'per_unit', 
                    'cost_per_unit': '3.0'
                }, follow_redirects=False)
                
                # Print response for debugging if needed
                print(f"Response status: {response.status_code}")
                if response.status_code != 302:  # Expected redirect after successful adjustment
                    print(f"Response data: {response.get_data(as_text=True)}")
                
                # Verify canonical service was called
                mock_process.assert_called_once()
                call_args = mock_process.call_args
                
                # Check the arguments passed to the function
                assert call_args[1]['item_id'] == test_item.id
                assert call_args[1]['quantity'] == 100.0
                assert call_args[1]['change_type'] == "restock"
                assert call_args[1]['unit'] == 'g'
                assert call_args[1]['notes'] == 'Initial stock'
                assert call_args[1]['created_by'] == test_user.id
                assert call_args[1]['cost_override'] == 3.0

# Original test case, kept for context or potential future use
def test_recount_adjustment_uses_canonical_service(client, app, test_user):
    """Test that inventory recount routes use the canonical adjustment service"""

    with app.app_context():
        # Create test inventory item
        item = InventoryItem(
            name="Test Item",
            quantity=100,
            unit="count",
            organization_id=test_user.organization_id
        )
        db.session.add(item)
        db.session.commit()

        # Log in the user for the test
        with client.session_transaction() as sess:
            sess['_user_id'] = str(test_user.id)
            sess['_fresh'] = True

        # Mock the canonical service at the route import path
        with patch('app.blueprints.inventory.routes.process_inventory_adjustment') as mock_adjustment:
            mock_adjustment.return_value = True

            # Make recount request
            response = client.post(f'/inventory/adjust/{item.id}', data={
                'adjustment_type': 'recount',
                'quantity': '80',
                'notes': 'Physical count adjustment'
            })

            # Verify canonical service was called
            mock_adjustment.assert_called_once()
            call_args = mock_adjustment.call_args

            assert call_args[1]['item_id'] == item.id
            assert call_args[1]['change_type'] == 'recount'
            assert 'Physical count' in call_args[1]['notes']