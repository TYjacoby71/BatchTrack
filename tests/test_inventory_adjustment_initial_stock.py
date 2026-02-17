from flask_login import login_user

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.inventory_lot import InventoryLot
from app.models.unified_inventory_history import UnifiedInventoryHistory
from app.models.models import Organization, User
from app.services.inventory_adjustment import create_inventory_item, process_inventory_adjustment, update_inventory_item
from app.services.inventory_adjustment._fifo_ops import INFINITE_ANCHOR_SOURCE_TYPE


def test_batch_deduction_does_not_create_initial_stock(app):
    with app.app_context():
        from app.models.permission import Permission
        from app.models.subscription_tier import SubscriptionTier

        org = Organization(name='Initial Stock Org')
        db.session.add(org)
        db.session.flush()

        track_quantity_perm = Permission.query.filter_by(name='inventory.track_quantities').first()
        if not track_quantity_perm:
            track_quantity_perm = Permission(
                name='inventory.track_quantities',
                description='Allow tracked inventory quantity deductions'
            )
            db.session.add(track_quantity_perm)
            db.session.flush()

        tier = SubscriptionTier(
            name=f'Tracked Tier {org.id}',
            billing_provider='exempt',
            user_limit=5
        )
        db.session.add(tier)
        db.session.flush()
        tier.permissions.append(track_quantity_perm)
        org.subscription_tier_id = tier.id

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
        assert usage_event.affected_lot_id is not None

        anchor_lot = db.session.get(InventoryLot, usage_event.affected_lot_id)
        assert anchor_lot is not None
        assert anchor_lot.source_type == INFINITE_ANCHOR_SOURCE_TYPE


def test_create_infinite_item_initializes_single_anchor_lot(app):
    with app.app_context():
        from app.models.permission import Permission
        from app.models.subscription_tier import SubscriptionTier

        org = Organization(name='Infinite Create Org')
        db.session.add(org)
        db.session.flush()

        track_quantity_perm = Permission.query.filter_by(name='inventory.track_quantities').first()
        if not track_quantity_perm:
            track_quantity_perm = Permission(
                name='inventory.track_quantities',
                description='Allow tracked inventory quantity deductions'
            )
            db.session.add(track_quantity_perm)
            db.session.flush()

        tier = SubscriptionTier(
            name=f'Infinite Create Tier {org.id}',
            billing_provider='exempt',
            user_limit=5
        )
        db.session.add(tier)
        db.session.flush()
        tier.permissions.append(track_quantity_perm)
        org.subscription_tier_id = tier.id

        user = User(
            email='infinite-create@test.com',
            username='infinite-create-user',
            organization_id=org.id,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        success, message, item_id = create_inventory_item(
            form_data={
                'name': 'Infinite Tap Water',
                'type': 'ingredient',
                'unit': 'g',
                'quantity': '0',
                'is_tracked': '0',
                'cost_entry_type': 'per_unit',
                'cost_per_unit': '0.02',
            },
            organization_id=org.id,
            created_by=user.id,
        )
        assert success is True, message
        assert item_id is not None

        created_item = db.session.get(InventoryItem, item_id)
        assert created_item is not None
        assert created_item.is_tracked is False
        assert float(created_item.quantity or 0.0) == 0.0

        anchor_lots = (
            InventoryLot.query
            .filter_by(inventory_item_id=item_id, source_type=INFINITE_ANCHOR_SOURCE_TYPE)
            .all()
        )
        assert len(anchor_lots) == 1
        assert int(anchor_lots[0].remaining_quantity_base or 0) == 0

        anchor_event = (
            UnifiedInventoryHistory.query
            .filter_by(inventory_item_id=item_id, change_type=INFINITE_ANCHOR_SOURCE_TYPE)
            .order_by(UnifiedInventoryHistory.id.desc())
            .first()
        )
        assert anchor_event is not None
        assert anchor_event.affected_lot_id == anchor_lots[0].id


def test_toggle_to_infinite_drains_remaining_lots(app):
    with app.app_context():
        from app.models.permission import Permission
        from app.models.subscription_tier import SubscriptionTier

        org = Organization(name='Toggle Infinite Org')
        db.session.add(org)
        db.session.flush()

        track_quantity_perm = Permission.query.filter_by(name='inventory.track_quantities').first()
        if not track_quantity_perm:
            track_quantity_perm = Permission(
                name='inventory.track_quantities',
                description='Allow tracked inventory quantity deductions'
            )
            db.session.add(track_quantity_perm)
            db.session.flush()

        tier = SubscriptionTier(
            name=f'Toggle Tier {org.id}',
            billing_provider='exempt',
            user_limit=5
        )
        db.session.add(tier)
        db.session.flush()
        tier.permissions.append(track_quantity_perm)
        org.subscription_tier_id = tier.id

        user = User(
            email='toggle@test.com',
            username='toggle-user',
            organization_id=org.id,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        item = InventoryItem(
            name='Tap Water',
            unit='g',
            quantity=0,
            is_tracked=True,
            cost_per_unit=0.03,
            organization_id=org.id,
            type='ingredient'
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

        with app.test_request_context():
            login_user(user)
            restock_success_a, _ = process_inventory_adjustment(
                item_id=item_id,
                change_type='restock',
                quantity=100,
                unit='g',
                notes='Opening lot A',
                created_by=user.id
            )
            restock_success_b, _ = process_inventory_adjustment(
                item_id=item_id,
                change_type='restock',
                quantity=40,
                unit='g',
                notes='Opening lot B',
                created_by=user.id
            )

        assert restock_success_a is True
        assert restock_success_b is True

        success, message = update_inventory_item(
            item_id,
            {'is_tracked': '0', 'confirm_infinite_drain': '1'},
            updated_by=user.id,
        )
        assert success is True, message

        item = db.session.get(InventoryItem, item_id)
        assert item is not None
        assert item.is_tracked is False
        assert float(item.quantity or 0.0) == 0.0

        lots = InventoryLot.query.filter_by(inventory_item_id=item_id).all()
        assert lots, "Expected at least one lot before/after toggle."
        anchor_lots = [lot for lot in lots if lot.source_type == INFINITE_ANCHOR_SOURCE_TYPE]
        finite_lots = [lot for lot in lots if lot.source_type != INFINITE_ANCHOR_SOURCE_TYPE]
        assert len(anchor_lots) == 1
        assert int(anchor_lots[0].remaining_quantity_base or 0) == 0
        assert all(int(lot.remaining_quantity_base or 0) == 0 for lot in finite_lots)

        drain_event = (
            UnifiedInventoryHistory.query
            .filter_by(inventory_item_id=item_id, change_type='toggle_infinite_drain')
            .order_by(UnifiedInventoryHistory.id.desc())
            .first()
        )
        assert drain_event is not None
        assert drain_event.quantity_change < 0
        assert drain_event.quantity_change_base < 0


def test_infinite_anchor_lot_is_reused_across_toggles(app):
    with app.app_context():
        from app.models.permission import Permission
        from app.models.subscription_tier import SubscriptionTier

        org = Organization(name='Infinite Anchor Reuse Org')
        db.session.add(org)
        db.session.flush()

        track_quantity_perm = Permission.query.filter_by(name='inventory.track_quantities').first()
        if not track_quantity_perm:
            track_quantity_perm = Permission(
                name='inventory.track_quantities',
                description='Allow tracked inventory quantity deductions'
            )
            db.session.add(track_quantity_perm)
            db.session.flush()

        tier = SubscriptionTier(
            name=f'Anchor Reuse Tier {org.id}',
            billing_provider='exempt',
            user_limit=5
        )
        db.session.add(tier)
        db.session.flush()
        tier.permissions.append(track_quantity_perm)
        org.subscription_tier_id = tier.id

        user = User(
            email='anchor-reuse@test.com',
            username='anchor-reuse-user',
            organization_id=org.id,
            is_verified=True
        )
        db.session.add(user)
        db.session.flush()

        item = InventoryItem(
            name='Reusable Infinite Water',
            unit='g',
            quantity=0,
            is_tracked=True,
            cost_per_unit=0.05,
            organization_id=org.id,
            type='ingredient'
        )
        db.session.add(item)
        db.session.commit()
        item_id = item.id

        with app.test_request_context():
            login_user(user)
            process_inventory_adjustment(
                item_id=item_id,
                change_type='restock',
                quantity=80,
                unit='g',
                notes='Finite lot before toggle',
                created_by=user.id
            )

        # First switch to infinite creates the anchor lot.
        success, message = update_inventory_item(
            item_id,
            {'is_tracked': '0', 'confirm_infinite_drain': '1'},
            updated_by=user.id,
        )
        assert success is True, message

        first_anchor = (
            InventoryLot.query
            .filter_by(inventory_item_id=item_id, source_type=INFINITE_ANCHOR_SOURCE_TYPE)
            .order_by(InventoryLot.id.asc())
            .first()
        )
        assert first_anchor is not None

        with app.test_request_context():
            login_user(user)
            process_inventory_adjustment(
                item_id=item_id,
                change_type='batch',
                quantity=25,
                unit='g',
                notes='Infinite deduction #1',
                created_by=user.id
            )

        first_usage = (
            UnifiedInventoryHistory.query
            .filter_by(inventory_item_id=item_id, change_type='batch')
            .order_by(UnifiedInventoryHistory.id.desc())
            .first()
        )
        assert first_usage is not None
        assert first_usage.affected_lot_id == first_anchor.id

        # Toggle back to finite and then to infinite again.
        success_back, message_back = update_inventory_item(
            item_id,
            {'is_tracked': '1'},
            updated_by=user.id,
        )
        assert success_back is True, message_back
        success_again, message_again = update_inventory_item(
            item_id,
            {'is_tracked': '0', 'confirm_infinite_drain': '1'},
            updated_by=user.id,
        )
        assert success_again is True, message_again

        anchors = (
            InventoryLot.query
            .filter_by(inventory_item_id=item_id, source_type=INFINITE_ANCHOR_SOURCE_TYPE)
            .all()
        )
        assert len(anchors) == 1
        assert anchors[0].id == first_anchor.id

        with app.test_request_context():
            login_user(user)
            process_inventory_adjustment(
                item_id=item_id,
                change_type='batch',
                quantity=30,
                unit='g',
                notes='Infinite deduction #2',
                created_by=user.id
            )

        second_usage = (
            UnifiedInventoryHistory.query
            .filter_by(inventory_item_id=item_id, change_type='batch')
            .order_by(UnifiedInventoryHistory.id.desc())
            .first()
        )
        assert second_usage is not None
        assert second_usage.affected_lot_id == first_anchor.id
