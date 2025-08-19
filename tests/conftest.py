"""
Pytest configuration and shared fixtures for BatchTrack tests.
"""
import os
import tempfile
import pytest
from app import create_app
from app.extensions import db
from app.models.models import User, Organization, SubscriptionTier, Permission, Role


@pytest.fixture(scope='function')  # Changed to function scope for isolation
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
        'LOGIN_DISABLED': False,  # Ensure authentication is active in tests
        'TESTING_DISABLE_AUTH': False  # Disable any test-specific auth bypass
        # Don't disable login - we need to test permissions properly
    })

    with app.app_context():
        db.create_all()

        # Create basic test data
        _create_test_data()

        yield app

        # Clean up database
        db.drop_all()

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
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def auth_headers():
    """Headers for authenticated requests."""
    return {'Content-Type': 'application/json'}


def _create_test_data():
    """Create basic test data with correct object relationships"""
    from app.models.subscription_tier import SubscriptionTier
    from app.models.models import Organization, User
    from app.extensions import db

    # Create a test subscription tier
    tier = SubscriptionTier(
        name='Test Tier',
        description='Test tier for testing',
        user_limit=5,
        is_customer_facing=True,
        billing_provider='exempt'
    )
    db.session.add(tier)
    db.session.commit()

    # Create a test organization - Pass the tier object, not tier.id
    org = Organization(
        name='Test Organization',
        subscription_tier=tier  # Pass the full object to the relationship
    )
    db.session.add(org)
    db.session.commit()

    # Create a test user
    user = User(
        email='test@example.com',
        username='testuser',  # Added username for completeness
        password_hash='test_hash',
        is_verified=True,
        organization_id=org.id  # This is correct - organization_id is a foreign key
    )
    db.session.add(user)
    db.session.commit()


@pytest.fixture
def test_org(db_session):
    org = Organization(name="Test Org")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def test_user(app):
    """Create a test customer user with basic permissions and organization"""
    with app.app_context():
        # Use unique username per test to avoid conflicts
        import time
        unique_username = f'testuser_{int(time.time() * 1000000)}'

        # Create a test organization with no hardcoded billing_status (will use model default)
        org = Organization(name='Test Organization')
        db.session.add(org)
        db.session.flush()  # Get the ID

        # Create a basic tier
        tier = SubscriptionTier(
            name='Basic',
            user_limit=5
        )
        db.session.add(tier)
        db.session.flush()

        # Assign tier to organization
        org.subscription_tier_id = tier.id

        user = User(
            username=unique_username,  # Use unique username
            email=f'{unique_username}@example.com',  # Use unique email too
            organization_id=org.id,
            user_type='customer',  # Explicitly set as customer
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        yield user

        # Cleanup is handled by the app fixture dropping all tables


@pytest.fixture
def developer_user(app):
    """Create a test developer user with no organization"""
    with app.app_context():
        # Use unique username per test to avoid conflicts
        import time
        unique_username = f'developer_{int(time.time() * 1000000)}'

        user = User(
            username=unique_username,
            email=f'{unique_username}@batchtrack.com',
            organization_id=None,  # Developers have no organization
            user_type='developer',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        yield user

        # Cleanup is handled by the app fixture dropping all tables