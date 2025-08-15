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
def db_session(app):
    with app.app_context():
        yield db.session
        db.session.rollback()


@pytest.fixture
def auth_headers():
    """Headers for authenticated requests."""
    return {'Content-Type': 'application/json'}


def _create_test_data():
    """Create basic test data"""
    from app.models.subscription_tier import SubscriptionTier
    from app.models.models import Organization, User
    from app.extensions import db

    # Create a test subscription tier
    tier = SubscriptionTier(
        name='Test Tier',
        key='test',
        max_users=5,
        max_monthly_batches=100,
        is_customer_facing=True
    )
    db.session.add(tier)
    db.session.commit()

    # Create a test organization
    org = Organization(
        name='Test Organization',
        subscription_tier=tier.id
    )
    db.session.add(org)
    db.session.commit()

    # Create a test user
    user = User(
        email='test@example.com',
        password_hash='test_hash',
        is_verified=True,
        organization_id=org.id
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
        # Create a test organization
        org = Organization(name='Test Organization', billing_status='active')
        db.session.add(org)
        db.session.flush()  # Get the ID

        # Create a basic tier
        tier = SubscriptionTier(
            name='Basic',
            key='basic',
            user_limit=5
        )
        db.session.add(tier)
        db.session.flush()

        # Assign tier to organization
        org.subscription_tier_id = tier.id

        user = User(
            username='testuser',
            email='test@example.com',
            organization_id=org.id,
            user_type='customer',  # Explicitly set as customer
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        yield user

        # Cleanup
        db.session.delete(user)
        db.session.delete(org)
        db.session.delete(tier)
        db.session.commit()

@pytest.fixture
def developer_user(app):
    """Create a test developer user with no organization"""
    with app.app_context():
        user = User(
            username='developer',
            email='dev@batchtrack.com',
            organization_id=None,  # Developers have no organization
            user_type='developer',
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        yield user

        # Cleanup
        db.session.delete(user)
        db.session.commit()