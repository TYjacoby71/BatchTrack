
"""
Pytest configuration and shared fixtures for BatchTrack tests.
"""
import os
import tempfile
import pytest
from app import create_app
from app.extensions import db
from app.models.models import User, Organization, SubscriptionTier, Permission, Role


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # Create a temporary file to use as the database
    db_fd, db_path = tempfile.mkstemp()
    
    app = create_app({
        'TESTING': True,
        'DATABASE_URL': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'STRIPE_SECRET_KEY': 'sk_test_fake',
        'STRIPE_WEBHOOK_SECRET': 'whsec_test_fake',
    })

    with app.app_context():
        db.create_all()
        
        # Create basic test data
        _create_test_data()
        
        yield app
        
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture
def auth_headers():
    """Headers for authenticated requests."""
    return {'Content-Type': 'application/json'}


def _create_test_data():
    """Create minimal test data for all tests."""
    # Create a test subscription tier
    tier = SubscriptionTier(
        tier_key='test_tier',
        name='Test Tier', 
        stripe_price_id_monthly='price_test_monthly',
        stripe_price_id_yearly='price_test_yearly',
        max_users=5,
        max_monthly_batches=100,
        is_customer_facing=True
    )
    db.session.add(tier)
    
    # Create a test organization
    org = Organization(
        name='Test Organization',
        subscription_tier_id='test_tier',
        stripe_customer_id='cus_test_customer'
    )
    db.session.add(org)
    
    # Create a test user
    user = User(
        email='test@example.com',
        password_hash='hashed_password',
        first_name='Test',
        last_name='User',
        organization_id=org.id,
        email_verified=True,
        is_active=True
    )
    db.session.add(user)
    
    db.session.commit()
