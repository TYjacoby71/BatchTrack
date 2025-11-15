from flask_login import login_user

from app.extensions import db
from app.models.inventory import InventoryItem
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
