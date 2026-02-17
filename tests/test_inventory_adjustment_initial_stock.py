from flask_login import login_user

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.unified_inventory_history import UnifiedInventoryHistory
from app.models.models import Organization, User
from app.services.inventory_adjustment import process_inventory_adjustment


def test_batch_deduction_does_not_create_initial_stock(app):
    with app.app_context():
        org = Organization(name='Initial Stock Org')
        db.session.add(org)
        db.session.flush()

        user = User(
            email='initial@test.com',
            username='initial-user',
            organization_id=org.id,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        ingredient = InventoryItem(
            name='First Use Oil',
            unit='g',
            quantity=0,
            organization_id=org.id,
            type='ingredient'
        )
        db.session.add(ingredient)
        db.session.commit()

        with app.test_request_context():
            login_user(user)

            success, message = process_inventory_adjustment(
            item_id=ingredient.id,
            change_type='batch',
            quantity=50,
            unit='g',
            notes='Test deduction',
            created_by=user.id
        )

        assert success is False
        assert ingredient.quantity == 0
        assert 'Insufficient' in (message or '').title() or 'error' in (message or '').lower()


def test_infinite_item_records_usage_without_quantity_change(app):
    with app.app_context():
        org = Organization(name='Infinite Item Org')
        db.session.add(org)
        db.session.flush()

        user = User(
            email='infinite@test.com',
            username='infinite-user',
            organization_id=org.id,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        water = InventoryItem(
            name='Tap Water',
            unit='g',
            quantity=0,
            is_tracked=False,
            cost_per_unit=0.02,
            organization_id=org.id,
            type='ingredient'
        )
        db.session.add(water)
        db.session.commit()
        water_id = water.id

        with app.test_request_context():
            login_user(user)
            success, message = process_inventory_adjustment(
                item_id=water_id,
                change_type='batch',
                quantity=150,
                unit='g',
                notes='Infinite water usage',
                created_by=user.id
            )

        water = db.session.get(InventoryItem, water_id)
        assert success is True
        assert 'quantity unchanged' in (message or '').lower()
        assert water.quantity == 0

        usage_event = (
            UnifiedInventoryHistory.query
            .filter_by(inventory_item_id=water_id, change_type='batch')
            .order_by(UnifiedInventoryHistory.id.desc())
            .first()
        )
        assert usage_event is not None
        assert usage_event.quantity_change < 0
        assert usage_event.quantity_change_base < 0
        assert usage_event.unit_cost == water.cost_per_unit
        assert 'Infinite item usage recorded' in (usage_event.notes or '')
