import pytest

from app.extensions import db
from app.models.product_category import ProductCategory
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
