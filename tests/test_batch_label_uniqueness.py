import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.batch import Batch
from app.models.models import Organization
from app.models.recipe import Recipe
from app.utils.timezone_utils import TimezoneUtils


def _make_recipe(name, label_prefix, organization_id):
    recipe = Recipe(
        name=name,
        label_prefix=label_prefix,
        predicted_yield=1.0,
        predicted_yield_unit="count",
        organization_id=organization_id,
    )
    db.session.add(recipe)
    db.session.flush()
    return recipe


def test_batch_labels_only_unique_within_org(app):
    with app.app_context():
        org_a = Organization(name="Org A")
        org_b = Organization(name="Org B")
        db.session.add_all([org_a, org_b])
        db.session.flush()

        recipe_a = _make_recipe("Apple Pie", "AP", org_a.id)
        recipe_b = _make_recipe("Apple Pie Copy", "AP", org_b.id)

        shared_label = "AP-2025-001"
        batch_a = Batch(
            recipe_id=recipe_a.id,
            label_code=shared_label,
            batch_type="product",
            organization_id=org_a.id,
            started_at=TimezoneUtils.utc_now(),
        )
        batch_b = Batch(
            recipe_id=recipe_b.id,
            label_code=shared_label,
            batch_type="product",
            organization_id=org_b.id,
            started_at=TimezoneUtils.utc_now(),
        )
        db.session.add_all([batch_a, batch_b])

        db.session.commit()

        assert batch_a.id is not None
        assert batch_b.id is not None
        assert batch_a.label_code == batch_b.label_code


def test_batch_labels_still_unique_inside_org(app):
    with app.app_context():
        org = Organization(name="Org Solo")
        db.session.add(org)
        db.session.flush()

        recipe = _make_recipe("Duplicate Label", "DUP", org.id)

        first_batch = Batch(
            recipe_id=recipe.id,
            label_code="DUP-2025-001",
            batch_type="product",
            organization_id=org.id,
            started_at=TimezoneUtils.utc_now(),
        )
        db.session.add(first_batch)
        db.session.commit()

        duplicate_batch = Batch(
            recipe_id=recipe.id,
            label_code="DUP-2025-001",
            batch_type="product",
            organization_id=org.id,
            started_at=TimezoneUtils.utc_now(),
        )
        db.session.add(duplicate_batch)

        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()
