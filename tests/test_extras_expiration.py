from flask_login import login_user

from app.extensions import db
from app.models.models import User, Organization
from app.models.inventory import InventoryItem
from app.models.recipe import Recipe
from app.services.batch_service.batch_operations import BatchOperationsService
from app.services.inventory_adjustment import process_inventory_adjustment
from app.utils.timezone_utils import TimezoneUtils
from datetime import timedelta


def _login_fresh_user(app):
    with app.app_context():
        org = Organization(name='OrgExpired')
        db.session.add(org)
        db.session.flush()

        user = User(email='expired@test.com', username='expired_user', organization_id=org.id, is_verified=True)
        db.session.add(user)
        db.session.commit()

        # Login within a request context
        with app.test_request_context('/'):
            login_user(user)
            yield user


def test_extras_cannot_consume_expired_lot(app):
    with app.app_context():
        # Login user
        user_gen = _login_fresh_user(app)
        user = next(user_gen)

        # Create perishable ingredient with default unit 'g'
        item = InventoryItem(
            name='Apple',
            unit='g',
            quantity=0,
            cost_per_unit=1.0,
            is_perishable=True,
            shelf_life_days=7,
            organization_id=user.organization_id
        )
        db.session.add(item)
        db.session.commit()

        # Restock with a lot that is already expired (custom expiration in past)
        past = TimezoneUtils.utc_now() - timedelta(days=1)
        ok, _ = process_inventory_adjustment(
            item_id=item.id,
            change_type='restock',
            quantity=100,
            unit='g',
            notes='expired stock',
            created_by=user.id,
            custom_expiration_date=past
        )
        assert ok

        # Create a recipe to start a batch (no base ingredients, we only test extras)
        recipe = Recipe(
            name='Test Recipe',
            predicted_yield=1.0,
            predicted_yield_unit='g',
            created_by=user.id,
            organization_id=user.organization_id
        )
        db.session.add(recipe)
        db.session.commit()

        # Start the batch
        with app.test_request_context('/'):
            login_user(user)
            batch, errs = BatchOperationsService.start_batch(recipe.id, scale=1.0)
            assert batch is not None
            assert errs == [] or isinstance(errs, list)

        # Attempt to add extras that match the expired lot quantity
        payload = {
            'extra_ingredients': [{
                'item_id': item.id,
                'quantity': 50,
                'unit': 'g'
            }],
            'extra_containers': [],
            'extra_consumables': []
        }

        # Call service directly
        with app.test_request_context('/'):
            login_user(user)
            success, message, errors = BatchOperationsService.add_extra_items_to_batch(
                batch_id=batch.id,
                extra_ingredients=payload['extra_ingredients'],
                extra_containers=payload['extra_containers'],
                extra_consumables=payload['extra_consumables']
            )

        # We expect failure because stock is expired and filtered out
        assert success is False
        assert errors and any('Not enough' in (e.get('message', '') if isinstance(e, dict) else str(e)) or 'stock' in (e.get('message', '') if isinstance(e, dict) else str(e)) for e in errors)

