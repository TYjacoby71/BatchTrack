import pytest

from app.extensions import db
from app.models.product_category import ProductCategory
from app.models.inventory import InventoryItem
from app.models.unit import Unit
from app.services.recipe_service._core import create_recipe
from app.services.recipe_service._validation import validate_recipe_data


@pytest.mark.usefixtures('app_context')
def test_create_draft_allows_missing_required_fields():
    category = ProductCategory(name='Draft Category')
    db.session.add(category)
    db.session.commit()

    ok, recipe = create_recipe(
        name='Draft Sample Recipe',
        instructions='Pending details',
        yield_amount=0,
        yield_unit='',
        ingredients=[],
        consumables=[],
        allowed_containers=[],
        label_prefix='DRFT',
        category_id=category.id,
        status='draft'
    )

    assert ok, f"Expected draft creation to succeed, got error: {recipe}"
    assert recipe.status == 'draft'
    assert recipe.test_sequence is None
    assert (recipe.predicted_yield or 0) == 0
    assert len(recipe.recipe_ingredients) == 0


@pytest.mark.usefixtures('app_context')
def test_validate_recipe_data_reports_missing_fields():
    result = validate_recipe_data(
        name='Publish Attempt',
        ingredients=[],
        yield_amount=0,
        portioning_data=None,
        allow_partial=False
    )

    assert not result['valid']
    assert 'yield amount' in result['missing_fields']
    assert 'ingredients' in result['missing_fields']


@pytest.mark.usefixtures('app_context')
def test_validate_recipe_data_uses_existing_portioning_state():
    category = ProductCategory(name='Portioned Drafts')
    db.session.add(category)
    unit = Unit.query.filter_by(name='oz').first()
    if not unit:
        unit = Unit(name='oz', unit_type='weight', base_unit='oz', conversion_factor=1.0, is_active=True, is_custom=False, is_mapped=True)
        db.session.add(unit)
    db.session.commit()

    ingredient = InventoryItem(name='Draft Ingredient', unit='oz', type='ingredient', quantity=1.0)
    db.session.add(ingredient)
    db.session.commit()

    ok, recipe = create_recipe(
        name='Portioned Draft Recipe',
        instructions='Pending',
        yield_amount=0,
        yield_unit='',
        ingredients=[{'item_id': ingredient.id, 'quantity': 1, 'unit': 'oz'}],
        allowed_containers=[],
        label_prefix='PRTD',
        category_id=category.id,
        portioning_data={
            'is_portioned': True,
            'portion_name': 'Bar',
            'portion_count': '',  # intentionally blank to simulate draft
            'portion_unit_id': None
        },
        status='draft'
    )
    assert ok, f"Failed to create draft recipe: {recipe}"
    assert recipe.is_portioned
    assert recipe.portion_count in (None, 0)
    assert recipe.test_sequence is None

    validation = validate_recipe_data(
        name=recipe.name,
        ingredients=[{'item_id': ingredient.id, 'quantity': 1, 'unit': 'oz'}],
        yield_amount=1,
        recipe_id=recipe.id,
        portioning_data=None,
        allow_partial=False
    )

    assert not validation['valid']
    assert 'portion count' in validation['missing_fields']
