from types import SimpleNamespace

from flask_login import login_user

from app.extensions import db
from app.models.recipe import Recipe, RecipeIngredient, RecipeConsumable
from app.models.inventory import InventoryItem
from app.models.models import Organization, User
from app.blueprints.batches.routes import api_start_batch
from app.services.batch_service import BatchOperationsService


def _build_recipe_with_missing_inventory():
    org = Organization(name='Gating Org')
    db.session.add(org)
    db.session.flush()

    user = User(
        email='gating@example.com',
        username='gating-user',
        organization_id=org.id,
        is_verified=True
    )
    db.session.add(user)
    db.session.flush()

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

    consumable_item = InventoryItem(
        name='Test Liner',
        unit='count',
        quantity=0,
        organization_id=org.id,
        type='consumable'
    )
    db.session.add(consumable_item)

    container_item = InventoryItem(
        name='Test Jar',
        unit='count',
        quantity=0,
        organization_id=org.id,
        type='container'
    )
    db.session.add(container_item)
    db.session.flush()

    recipe_ingredient = RecipeIngredient(
        recipe_id=recipe.id,
        inventory_item_id=ingredient.id,
        quantity=100,
        unit='g',
        organization_id=org.id
    )
    db.session.add(recipe_ingredient)

    recipe_consumable = RecipeConsumable(
        recipe_id=recipe.id,
        inventory_item_id=consumable_item.id,
        quantity=5,
        unit='count',
        organization_id=org.id
    )
    db.session.add(recipe_consumable)
    db.session.commit()

    return user, recipe, ingredient.id, consumable_item.id, container_item.id


def test_api_start_batch_requires_override_before_force(app, monkeypatch):
    with app.app_context():
        user, recipe, ingredient_id, consumable_id, container_id = _build_recipe_with_missing_inventory()

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
            'recipe_id': recipe.id,
            'scale': 1.0,
            'batch_type': 'ingredient',
            'notes': '',
            'containers': [{'id': container_id, 'quantity': 1}]
        }

        with app.test_request_context('/batches/api/start-batch', method='POST', json=payload):
            login_user(user)
            response = api_start_batch()
            data = response.get_json()
            assert data['requires_override'] is True
            assert data['success'] is False
            assert data['stock_issues'], "Expected stock issues to be returned when gating triggers"

        payload['force_start'] = True
        with app.test_request_context('/batches/api/start-batch', method='POST', json=payload):
            login_user(user)
            response = api_start_batch()
            data = response.get_json()
            assert data['success'] is True
            assert data['batch_id'] == 555

        plan_snapshot = captured_plan['value']
        assert plan_snapshot.get('skip_ingredient_ids') == [ingredient_id]
        assert plan_snapshot.get('skip_consumable_ids') == [consumable_id]
        assert plan_snapshot.get('skip_container_ids') == [container_id]
        summary = plan_snapshot.get('forced_start_summary')
        assert summary and 'Started batch without:' in summary
        assert 'Test Oil' in summary
