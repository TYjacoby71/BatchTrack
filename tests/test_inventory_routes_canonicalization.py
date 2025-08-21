import pytest
from unittest.mock import patch, MagicMock
from app import create_app
from app.extensions import db
from app.models.models import User, Organization, InventoryItem


# Helper function to create a mock user with organization
def mock_user_with_org():
    mock_user = MagicMock(spec=User)
    mock_user.id = 1
    mock_user.organization_id = 1
    mock_user.is_authenticated = True
    mock_user.user_type = 'regular'
    mock_user.organization = MagicMock(spec=Organization)
    mock_user.organization.is_active = True
    return mock_user


class TestInventoryRoutesCanonicalService:
    """Verify inventory routes use canonical inventory adjustment service"""

    @pytest.fixture
    def app(self):
        app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:'})
        with app.app_context():
            # Create all database tables
            db.create_all()
        return app

    @pytest.fixture
    def client(self, app):
        return app.test_client()

    def test_adjust_inventory_initial_stock_calls_canonical_service(self, client, app):
        """Test that initial stock adjustment for a new item uses the canonical service."""
        with app.app_context():
            # ARRANGE: Create a real, valid user and item for this test.
            # This is more robust than complex mocking.
            from app.models import db, InventoryItem, User, Organization, SubscriptionTier

            tier = SubscriptionTier(name="Test Tier", tier_type="monthly", user_limit=5)
            db.session.add(tier)
            db.session.flush()

            org = Organization(name="Test Org", billing_status='active', subscription_tier_id=tier.id)
            db.session.add(org)
            db.session.flush()

            user = User(username="inventory_tester", email="inv@test.com", organization_id=org.id)
            db.session.add(user)
            db.session.flush()

            item = InventoryItem(name="New Item", unit="g", organization_id=org.id)
            db.session.add(item)
            db.session.commit()

            # Log in our real test user
            with client.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True

            # Patch only the canonical service, which is what we want to test.
            with patch('app.blueprints.inventory.routes.process_inventory_adjustment') as mock_process:
                mock_process.return_value = (True, "Success")  # Return a tuple

                # ACT
                response = client.post(f'/inventory/adjust/{item.id}', data={
                    'change_type': 'restock',
                    'quantity': '100.0',
                    'input_unit': 'g',
                    'cost_entry_type': 'no_change',
                    'notes': 'Initial stock'
                })

                # ASSERT
                # 1. The service was called exactly once.
                mock_process.assert_called_once()

                # 2. The user was redirected back to the item page, indicating success.
                assert response.status_code == 302
                assert f'/inventory/view/{item.id}' in response.location

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
            mock_adjustment.return_value = (True, "Recount successful")

            # Make recount request
            response = client.post(f'/inventory/adjust/{item.id}', data={
                'change_type': 'recount',
                'quantity': '80',
                'notes': 'Physical count adjustment'
            })

            # Verify canonical service was called
            mock_adjustment.assert_called_once()
            call_args = mock_adjustment.call_args

            assert call_args[1]['item_id'] == item.id
            assert call_args[1]['change_type'] == 'recount'
            assert 'Physical count' in call_args[1]['notes']