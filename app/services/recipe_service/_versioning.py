"""Recipe versioning helpers for tests and promotions.

Synopsis:
Create tests and promote versions within or across recipe groups.

Glossary:
- Test: Editable, non-current version.
- Promotion: Move a version into current/master status.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

import sqlalchemy as sa

from ...extensions import db
from ...models import Recipe, RecipeIngredient, RecipeConsumable
from ._core import create_recipe

logger = logging.getLogger(__name__)


# --- Build test template ---
# Purpose: Build a test recipe template from a base.
def build_test_template(base: Recipe) -> Recipe:
    template = Recipe(
        name=base.name,
        instructions=base.instructions,
        label_prefix=base.label_prefix,
        predicted_yield=base.predicted_yield,
        predicted_yield_unit=base.predicted_yield_unit,
        category_id=base.category_id,
    )
    template.recipe_group_id = base.recipe_group_id
    template.is_master = base.is_master
    template.variation_name = base.variation_name
    template.variation_prefix = base.variation_prefix
    template.parent_recipe_id = base.parent_recipe_id
    template.parent_master_id = base.parent_master_id
    template.portioning_data = (
        base.portioning_data.copy() if isinstance(base.portioning_data, dict) else base.portioning_data
    )
    template.is_portioned = base.is_portioned
    template.portion_name = base.portion_name
    template.portion_count = base.portion_count
    template.portion_unit_id = base.portion_unit_id
    if base.category_data:
        template.category_data = (
            base.category_data.copy() if isinstance(base.category_data, dict) else base.category_data
        )
    template.skin_opt_in = base.skin_opt_in
    template.sharing_scope = 'private'
    template.is_public = False
    template.is_for_sale = False
    return template


# --- Create test version ---
# Purpose: Create a test version from a base recipe.
def create_test_version(base: Recipe, payload: Dict[str, Any], target_status: str) -> Tuple[bool, Any]:
    test_payload = dict(payload)
    test_payload.update(
        {
            "status": target_status,
            "is_test": True,
            "recipe_group_id": base.recipe_group_id,
            "variation_name": base.variation_name,
            "parent_master_id": base.parent_master_id,
            "parent_recipe_id": base.parent_recipe_id,
            "version_number_override": base.version_number,
            "sharing_scope": "private",
            "is_public": False,
            "is_for_sale": False,
            "marketplace_status": "draft",
        }
    )
    return create_recipe(**test_payload)


# --- Promote test ---
# Purpose: Promote a test to the current version.
def promote_test_to_current(recipe_id: int) -> Tuple[bool, Any]:
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe or recipe.test_sequence is None:
        return False, "Test version not found."

    base_query = Recipe.query.filter(
        Recipe.recipe_group_id == recipe.recipe_group_id,
        Recipe.is_master.is_(recipe.is_master),
        Recipe.test_sequence.is_(None),
    )
    if not recipe.is_master:
        base_query = base_query.filter(Recipe.variation_name == recipe.variation_name)
    max_version = base_query.with_entities(sa.func.max(Recipe.version_number)).scalar() or 0

    recipe.version_number = int(max_version) + 1
    recipe.test_sequence = None
    recipe.status = "published"
    recipe.sharing_scope = "private"
    recipe.is_public = False
    recipe.is_for_sale = False
    recipe.sale_price = None
    recipe.marketplace_status = "draft"
    db.session.commit()
    return True, recipe


# --- Unique recipe name ---
# Purpose: Generate a unique recipe name within an org.
def _unique_recipe_name(base_name: str, org_id: int | None) -> str:
    if not org_id:
        return base_name
    candidate = base_name
    suffix = 1
    while Recipe.query.filter(
        Recipe.organization_id == org_id,
        Recipe.name == candidate,
    ).first():
        suffix += 1
        candidate = f"{base_name} (New Group {suffix})"
    return candidate


# --- Promote to master ---
# Purpose: Promote a variation to master in the same group.
def promote_variation_to_master(recipe_id: int) -> Tuple[bool, Any]:
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe or recipe.is_master or recipe.test_sequence is not None:
        return False, "Only published variations can be promoted to master."

    max_version = (
        Recipe.query.filter(
            Recipe.recipe_group_id == recipe.recipe_group_id,
            Recipe.is_master.is_(True),
            Recipe.test_sequence.is_(None),
        )
        .with_entities(sa.func.max(Recipe.version_number))
        .scalar()
        or 0
    )
    next_version = int(max_version) + 1

    ingredients_payload = [
        {
            "item_id": assoc.inventory_item_id,
            "quantity": assoc.quantity,
            "unit": assoc.unit,
        }
        for assoc in recipe.recipe_ingredients
    ]
    consumables_payload = [
        {
            "item_id": assoc.inventory_item_id,
            "quantity": assoc.quantity,
            "unit": assoc.unit,
        }
        for assoc in recipe.recipe_consumables
    ]
    master_name = recipe.recipe_group.name if recipe.recipe_group else recipe.name
    return create_recipe(
        name=master_name,
        instructions=recipe.instructions,
        yield_amount=recipe.predicted_yield or 0.0,
        yield_unit=recipe.predicted_yield_unit or "",
        ingredients=ingredients_payload,
        consumables=consumables_payload,
        allowed_containers=list(recipe.allowed_containers or []),
        label_prefix=recipe.label_prefix or "",
        category_id=recipe.category_id,
        portioning_data=recipe.portioning_data,
        is_portioned=recipe.is_portioned,
        portion_name=recipe.portion_name,
        portion_count=recipe.portion_count,
        portion_unit_id=recipe.portion_unit_id,
        status="published",
        recipe_group_id=recipe.recipe_group_id,
        version_number_override=next_version,
        sharing_scope="private",
        is_public=False,
        is_for_sale=False,
        marketplace_status="draft",
    )


# --- Promote to new group ---
# Purpose: Promote a variation to a new recipe group.
def promote_variation_to_new_group(recipe_id: int) -> Tuple[bool, Any]:
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe or recipe.is_master or recipe.test_sequence is not None:
        return False, "Only published variations can start a new recipe group."

    ingredients_payload = [
        {
            "item_id": assoc.inventory_item_id,
            "quantity": assoc.quantity,
            "unit": assoc.unit,
        }
        for assoc in recipe.recipe_ingredients
    ]
    consumables_payload = [
        {
            "item_id": assoc.inventory_item_id,
            "quantity": assoc.quantity,
            "unit": assoc.unit,
        }
        for assoc in recipe.recipe_consumables
    ]
    candidate_name = _unique_recipe_name(recipe.name or "New Recipe Group", recipe.organization_id)

    return create_recipe(
        name=candidate_name,
        instructions=recipe.instructions,
        yield_amount=recipe.predicted_yield or 0.0,
        yield_unit=recipe.predicted_yield_unit or "",
        ingredients=ingredients_payload,
        consumables=consumables_payload,
        allowed_containers=list(recipe.allowed_containers or []),
        label_prefix="",
        category_id=recipe.category_id,
        portioning_data=recipe.portioning_data,
        is_portioned=recipe.is_portioned,
        portion_name=recipe.portion_name,
        portion_count=recipe.portion_count,
        portion_unit_id=recipe.portion_unit_id,
        status="published",
        sharing_scope="private",
        is_public=False,
        is_for_sale=False,
        marketplace_status="draft",
    )


__all__ = [
    "build_test_template",
    "create_test_version",
    "promote_test_to_current",
    "promote_variation_to_master",
    "promote_variation_to_new_group",
]
