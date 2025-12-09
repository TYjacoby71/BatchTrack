import pytest

from app.extensions import db
from app.models import InventoryItem, Organization, Unit
from app.services.recipe_proportionality_service import RecipeProportionalityService


def _ensure_unit(name: str, unit_type: str, conversion_factor: float, base_unit: str | None = None):
    unit = Unit.query.filter_by(name=name).first()
    if unit:
        return unit
    unit = Unit(
        name=name,
        unit_type=unit_type,
        conversion_factor=conversion_factor,
        base_unit=base_unit,
        is_active=True,
        is_custom=False,
    )
    db.session.add(unit)
    db.session.commit()
    return unit


@pytest.mark.usefixtures("app_context")
def test_proportionality_matches_scaled_payloads():
    _ensure_unit('gram', 'weight', 1.0, None)
    _ensure_unit('ounce', 'weight', 28.3495, 'gram')

    org = Organization.query.first()
    ingredient = InventoryItem(
        name="Sugar",
        unit='gram',
        type='ingredient',
        quantity=0.0,
        organization_id=org.id if org else None,
    )
    db.session.add(ingredient)
    db.session.commit()

    payload_a = [{'item_id': ingredient.id, 'quantity': 100.0, 'unit': 'gram'}]
    payload_b = [{'item_id': ingredient.id, 'quantity': 3.527396, 'unit': 'ounce'}]

    assert RecipeProportionalityService.are_recipes_proportionally_identical(payload_a, payload_b)


@pytest.mark.usefixtures("app_context")
def test_proportionality_detects_ratio_changes():
    _ensure_unit('gram', 'weight', 1.0, None)

    org = Organization.query.first()
    sugar = InventoryItem(
        name="Sugar",
        unit='gram',
        type='ingredient',
        quantity=0.0,
        organization_id=org.id if org else None,
    )
    oil = InventoryItem(
        name="Oil",
        unit='gram',
        type='ingredient',
        quantity=0.0,
        organization_id=org.id if org else None,
    )
    db.session.add_all([sugar, oil])
    db.session.commit()

    base = [
        {'item_id': sugar.id, 'quantity': 50.0, 'unit': 'gram'},
        {'item_id': oil.id, 'quantity': 50.0, 'unit': 'gram'},
    ]
    changed = [
        {'item_id': sugar.id, 'quantity': 60.0, 'unit': 'gram'},
        {'item_id': oil.id, 'quantity': 40.0, 'unit': 'gram'},
    ]

    assert not RecipeProportionalityService.are_recipes_proportionally_identical(base, changed)
