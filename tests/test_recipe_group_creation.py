"""Tests for recipe group creation contention safeguards."""

from uuid import uuid4

import pytest

from app.extensions import db
from app.models.models import Organization
from app.models.recipe import RecipeGroup
from app.services.recipe_service._core import _ensure_recipe_group


def _token(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


@pytest.mark.usefixtures("app_context")
def test_ensure_recipe_group_returns_existing_by_name():
    org = Organization.query.first()
    assert org is not None

    group_name = _token("Existing Group")
    existing = RecipeGroup(
        organization_id=org.id,
        name=group_name,
        prefix=_token("EX").replace("-", "")[:8].upper(),
    )
    db.session.add(existing)
    db.session.commit()

    ensured = _ensure_recipe_group(
        recipe_org_id=org.id,
        group_name=group_name,
    )
    db.session.commit()

    assert ensured.id == existing.id
    assert (
        RecipeGroup.query.filter_by(organization_id=org.id, name=group_name).count() == 1
    )


@pytest.mark.usefixtures("app_context")
def test_ensure_recipe_group_regenerates_taken_prefix():
    org = Organization.query.first()
    assert org is not None

    taken_prefix = "TAKEN01"
    existing = RecipeGroup(
        organization_id=org.id,
        name=_token("Prefix Source"),
        prefix=taken_prefix,
    )
    db.session.add(existing)
    db.session.commit()

    new_group = _ensure_recipe_group(
        recipe_org_id=org.id,
        group_name=_token("Prefix Target"),
        group_prefix=taken_prefix,
    )
    db.session.commit()

    assert new_group.id != existing.id
    assert new_group.prefix != taken_prefix
    assert len(new_group.prefix) <= 8
