import pytest
from flask_login import login_user

from app.extensions import db
from app.models import Batch, Product, ProductCategory, ProductVariant, Recipe
from app.models.models import User
from app.services.batch_service.batch_operations import BatchOperationsService


def _setup_recipe_for_user(user, name: str, label_prefix: str) -> Recipe:
    category = ProductCategory.query.filter_by(name='Uncategorized').first()
    recipe = Recipe(
        name=name,
        label_prefix=label_prefix,
        category_id=category.id,
        organization_id=user.organization_id,
        created_by=user.id
    )
    db.session.add(recipe)
    db.session.flush()
    return recipe


@pytest.mark.usefixtures('app_context')
def test_complete_batch_surfaces_adjustment_failure_for_ingredient(app, monkeypatch):
    """Finish should fail instead of flashing success when inventory credit fails."""
    with app.test_request_context('/'):
        user = User.query.first()
        login_user(user)

        recipe = _setup_recipe_for_user(user, 'Intermediate Failure Recipe', 'INTFAIL')
        batch = Batch(
            recipe_id=recipe.id,
            label_code='INTFAIL-001',
            batch_type='ingredient',
            status='in_progress',
            organization_id=user.organization_id,
            created_by=user.id
        )
        db.session.add(batch)
        db.session.commit()

        from app.blueprints.batches import finish_batch as finish_batch_module
        monkeypatch.setattr(
            finish_batch_module,
            'process_inventory_adjustment',
            lambda **kwargs: (False, 'forced adjustment failure')
        )

        success, message = BatchOperationsService.complete_batch(batch.id, {
            'output_type': 'ingredient',
            'final_quantity': '8',
            'output_unit': 'oz'
        })

        db.session.refresh(batch)
        assert success is False
        assert 'forced adjustment failure' in message
        assert batch.status == 'in_progress'


@pytest.mark.usefixtures('app_context')
def test_complete_batch_fails_when_portion_credit_fails(app, monkeypatch):
    """Portion SKU credit errors must fail completion (not silently succeed)."""
    with app.test_request_context('/'):
        user = User.query.first()
        login_user(user)

        category = ProductCategory.query.filter_by(name='Uncategorized').first()
        recipe = _setup_recipe_for_user(user, 'Portion Failure Recipe', 'PRTFAIL')
        product = Product(
            name='Portion Failure Product',
            category_id=category.id,
            organization_id=user.organization_id,
            created_by=user.id
        )
        db.session.add(product)
        db.session.flush()
        variant = ProductVariant(
            product_id=product.id,
            name='Base',
            organization_id=user.organization_id,
            created_by=user.id
        )
        db.session.add(variant)
        db.session.flush()

        batch = Batch(
            recipe_id=recipe.id,
            label_code='PRTFAIL-001',
            batch_type='product',
            status='in_progress',
            organization_id=user.organization_id,
            created_by=user.id,
            is_portioned=True,
            portion_name='Bar'
        )
        db.session.add(batch)
        db.session.commit()

        from app.blueprints.batches import finish_batch as finish_batch_module
        monkeypatch.setattr(
            finish_batch_module,
            'process_inventory_adjustment',
            lambda **kwargs: (False, 'forced portion credit failure')
        )

        success, message = BatchOperationsService.complete_batch(batch.id, {
            'output_type': 'product',
            'product_id': product.id,
            'variant_id': variant.id,
            'final_quantity': '4',
            'output_unit': 'oz',
            'final_portions': '8'
        })

        db.session.refresh(batch)
        assert success is False
        assert 'forced portion credit failure' in message
        assert batch.status == 'in_progress'
