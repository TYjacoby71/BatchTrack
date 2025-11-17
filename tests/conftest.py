"""
Pytest configuration and shared fixtures for BatchTrack tests.
"""
import os
import tempfile
import pytest
from sqlalchemy import inspect, text
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
        # Prefer Alembic migrations to build schema if available; fallback to create_all for unit tests
        try:
            os.environ.setdefault('SQLALCHEMY_DISABLE_CREATE_ALL', '1')
            # Build schema solely via migrations for closer prod parity
            from flask.cli import ScriptInfo
            # Invoke upgrade programmatically
            from flask_migrate import upgrade
            upgrade()
        except Exception:
            # If migrations are not runnable in test context, fall back to create_all
            os.environ.pop('SQLALCHEMY_DISABLE_CREATE_ALL', None)
            db.create_all()

        _ensure_sqlite_schema_columns()

        # Create basic test data
        _create_test_data()

    yield app

    # Clean up database
    with app.app_context():
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
    """Provides a database session for tests with rollback."""
    with app.app_context():
        # Run Alembic migrations to ensure schema is up to date
        from alembic import command
        from alembic.config import Config
        import os

        # Get the migrations directory
        migrations_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'migrations')
        alembic_cfg = Config(os.path.join(migrations_dir, 'alembic.ini'))
        alembic_cfg.set_main_option('script_location', migrations_dir)

        try:
            # Upgrade to head to ensure all migrations are applied
            command.upgrade(alembic_cfg, 'head')
        except Exception as e:
            # Fallback to create_all if migrations fail
            print(f"Migration failed, falling back to create_all: {e}")
            db.create_all()

        yield db.session
        db.session.rollback()

        # Clean up - drop all tables
        try:
            command.downgrade(alembic_cfg, 'base')
        except Exception:
            db.drop_all()


@pytest.fixture
def app_context(app):
    """Provide an application context for tests that need it."""
    with app.app_context():
        yield


@pytest.fixture
def auth_headers():
    """Headers for authenticated requests."""
    return {'Content-Type': 'application/json'}


def _create_test_data():
    """Create basic test data with correct object relationships"""
    from app.models.subscription_tier import SubscriptionTier
    from app.models.models import Organization, User
    from app.models.product_category import ProductCategory
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

    # Ensure a default product category exists for tests
    if not ProductCategory.query.filter_by(name='Uncategorized').first():
        db.session.add(ProductCategory(name='Uncategorized'))
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


def _ensure_sqlite_schema_columns():
    """SQLite migrations can drop renamed columns; ensure critical columns exist for tests."""
    inspector = inspect(db.engine)

    def ensure_columns(table_name: str, column_defs: dict[str, str]):
        nonlocal inspector
        try:
            existing = {col['name'] for col in inspector.get_columns(table_name)}
        except Exception:
            return
        missing = {name: ddl for name, ddl in column_defs.items() if name not in existing}
        if not missing:
            return
        for column_name, ddl in missing.items():
            db.session.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN {column_name} {ddl}'))
        db.session.commit()
        inspector = inspect(db.engine)

    from app.models.recipe import RecipeLineage
    RecipeLineage.__table__.create(db.engine, checkfirst=True)

    ensure_columns('user', {
        'active_session_token': 'VARCHAR(255)'
    })

    ensure_columns('recipe', {
        'parent_recipe_id': 'INTEGER',
        'cloned_from_id': 'INTEGER',
        'root_recipe_id': 'INTEGER'
    })

    ensure_columns('inventory_item', {
        'recommended_fragrance_load_pct': 'VARCHAR(64)',
        'inci_name': 'VARCHAR(256)',
        'protein_content_pct': 'FLOAT',
        'brewing_color_srm': 'FLOAT',
        'brewing_potential_sg': 'FLOAT',
        'brewing_diastatic_power_lintner': 'FLOAT',
        'fatty_acid_profile': 'TEXT',
        'certifications': 'TEXT'
    })

    ensure_columns('global_item', {
        'aliases': 'TEXT',
        'recommended_shelf_life_days': 'INTEGER',
        'recommended_usage_rate': 'VARCHAR(64)',
        'recommended_fragrance_load_pct': 'VARCHAR(64)',
        'is_active_ingredient': 'BOOLEAN',
        'inci_name': 'VARCHAR(256)',
        'certifications': 'TEXT',
        'capacity': 'FLOAT',
        'capacity_unit': 'VARCHAR(32)',
        'container_material': 'VARCHAR(64)',
        'container_type': 'VARCHAR(64)',
        'container_style': 'VARCHAR(64)',
        'container_color': 'VARCHAR(64)',
        'saponification_value': 'FLOAT',
        'iodine_value': 'FLOAT',
        'melting_point_c': 'FLOAT',
        'flash_point_c': 'FLOAT',
        'ph_value': 'VARCHAR(32)',
        'ph_min': 'FLOAT',
        'ph_max': 'FLOAT',
        'moisture_content_percent': 'FLOAT',
        'comedogenic_rating': 'INTEGER',
        'fatty_acid_profile': 'TEXT',
        'protein_content_pct': 'FLOAT',
        'brewing_color_srm': 'FLOAT',
        'brewing_potential_sg': 'FLOAT',
        'brewing_diastatic_power_lintner': 'FLOAT',
        'metadata_json': 'TEXT',
        'is_archived': 'BOOLEAN',
        'archived_at': 'DATETIME',
        'archived_by': 'INTEGER'
    })


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