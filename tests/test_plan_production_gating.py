from types import SimpleNamespace

from flask_login import login_user

from app.extensions import db
from app.models.recipe import Recipe, RecipeIngredient, RecipeConsumable
from app.models.inventory import InventoryItem
from app.models.models import Organization, User
from app.blueprints.batches.routes import api_start_batch
from app.services.batch_service import BatchOperationsService


def _build_recipe_with_missing_inventory(*, include_output_tracking: bool = True):
    from app.models.permission import Permission
    from app.models.subscription_tier import SubscriptionTier
    from app.models.role import Role

    org = Organization(name='Gating Org')
    db.session.add(org)
    db.session.flush()

    perm = Permission.query.filter_by(name='batches.create').first()
    if not perm:
        perm = Permission(name='batches.create', description='Start production batches')
        db.session.add(perm)
        db.session.flush()
    output_tracking_perm = Permission.query.filter_by(name='batches.track_inventory_outputs').first()
    if include_output_tracking and not output_tracking_perm:
        output_tracking_perm = Permission(
            name='batches.track_inventory_outputs',
            description='Allow tracked batch outputs'
        )
        db.session.add(output_tracking_perm)
        db.session.flush()

    tier = SubscriptionTier(
        name='Gating Tier',
        billing_provider='exempt',
        user_limit=5
    )
    db.session.add(tier)
    db.session.flush()
    tier.permissions.append(perm)
    if include_output_tracking and output_tracking_perm:
        tier.permissions.append(output_tracking_perm)
    org.subscription_tier_id = tier.id

    user = User(
        email='gating@example.com',
        username='gating-user',
        organization_id=org.id,
        is_verified=True
    )
    db.session.add(user)
    db.session.flush()
    org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    if org_owner_role:
        user.assign_role(org_owner_role)

    recipe = Recipe(
        name='Gated Recipe',
        predicted_yield=10,
        predicted_yield_unit='g',
        organization_id=org.id,
        created_by=user.id
    )
    db.session.add(recipe)
    db.session.flush()

    ingredient = InventoryItem(
        name='Test Oil',
        unit='g',
        quantity=0,
        organization_id=org.id,
        type='ingredient'
    )
    db.session.add(ingredient)
    db.session.flush()

    recipe_ingredient = RecipeIngredient(
        recipe_id=recipe.id,
        inventory_item_id=ingredient.id,
        quantity=100,
        unit='g',
        organization_id=org.id
    )
    db.session.add(recipe_ingredient)

    consumable = InventoryItem(
        name='Test Label Roll',
        unit='count',
        quantity=0,
        organization_id=org.id,
        type='consumable'
    )
    db.session.add(consumable)
    db.session.flush()

    recipe_consumable = RecipeConsumable(
        recipe_id=recipe.id,
        inventory_item_id=consumable.id,
        quantity=5,
        unit='count',
        organization_id=org.id
    )
    db.session.add(recipe_consumable)
    db.session.commit()

    return user.id, recipe.id, ingredient.id, consumable.id


def test_api_start_batch_requires_override_before_force(app, monkeypatch):
    app.config['SKIP_PERMISSIONS'] = True
    with app.app_context():
        user_id, recipe_id, ingredient_id, consumable_id = _build_recipe_with_missing_inventory(
            include_output_tracking=True
        )

        captured_plan = {}

        def fake_start_batch(cls, plan_snapshot):
            captured_plan['value'] = plan_snapshot
            return SimpleNamespace(id=555), []

        monkeypatch.setattr(
            BatchOperationsService,
            'start_batch',
            classmethod(fake_start_batch)
        )

        payload = {
            'recipe_id': recipe_id,
            'scale': 1.0,
            'batch_type': 'ingredient',
            'notes': '',
            'containers': []
        }

        with app.test_request_context('/batches/api/start-batch', method='POST', json=payload):
            login_user(db.session.get(User, user_id))
            response = api_start_batch()
            data = response.get_json()
            assert data['requires_override'] is True
            assert data['success'] is False
            assert data['stock_issues'], "Expected stock issues to be returned when gating triggers"

        payload['force_start'] = True
        with app.test_request_context('/batches/api/start-batch', method='POST', json=payload):
            login_user(db.session.get(User, user_id))
            response = api_start_batch()
            data = response.get_json()
            assert data['success'] is True
            assert data['batch_id'] == 555

        plan_snapshot = captured_plan['value']
        assert plan_snapshot.get('skip_ingredient_ids') == [ingredient_id]
        assert plan_snapshot.get('skip_consumable_ids') == [consumable_id]
        summary = plan_snapshot.get('forced_start_summary')
        assert summary and 'Started batch without:' in summary
        assert 'Test Oil' in summary
        assert 'Test Label Roll' in summary


def test_api_start_batch_forces_untracked_when_output_tracking_tier_permission_missing(app, monkeypatch):
    app.config['SKIP_PERMISSIONS'] = True
    with app.app_context():
        user_id, recipe_id, ingredient_id, consumable_id = _build_recipe_with_missing_inventory(
            include_output_tracking=False
        )

        captured_plan = {}

        def fake_start_batch(cls, plan_snapshot):
            captured_plan['value'] = plan_snapshot
            return SimpleNamespace(id=777), []

        monkeypatch.setattr(
            BatchOperationsService,
            'start_batch',
            classmethod(fake_start_batch)
        )

        payload = {
            'recipe_id': recipe_id,
            'scale': 1.0,
            'batch_type': 'product',
            'notes': '',
            'containers': []
        }

        with app.test_request_context('/batches/api/start-batch', method='POST', json=payload):
            login_user(db.session.get(User, user_id))
            response = api_start_batch()
            data = response.get_json()
            assert data['success'] is True
            assert data['batch_id'] == 777

        plan_snapshot = captured_plan['value']
        assert plan_snapshot.get('batch_type') == 'untracked'
        assert plan_snapshot.get('skip_ingredient_ids') in (None, [])
        assert plan_snapshot.get('skip_consumable_ids') in (None, [])
        assert plan_snapshot.get('forced_start_summary') in (None, '')
