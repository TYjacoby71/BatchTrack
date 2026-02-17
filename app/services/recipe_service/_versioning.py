"""Recipe versioning helpers for tests and promotions.

Synopsis:
Create tests and promote versions within or across recipe groups with explicit naming.

Glossary:
- Test: Editable, non-current version.
- Promotion: Move a version into current/master status.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Tuple

import sqlalchemy as sa

from ...extensions import db
from ...models import Recipe
from ._core import _next_test_sequence, create_recipe
from ._current import apply_current_flag
from ._lineage import _log_lineage_event

logger = logging.getLogger(__name__)
_TEST_SUFFIX_PATTERN = re.compile(r"\s*-\s*test\s+\d+\s*$", re.IGNORECASE)


# --- Strip test suffix ---
# Purpose: Remove a trailing " - Test N" marker from a recipe name.
# Inputs: Raw recipe name string, which may include a test suffix.
# Outputs: Normalized base name without the trailing test marker.
def _strip_test_suffix(value: str | None) -> str:
    if not value:
        return ""
    return _TEST_SUFFIX_PATTERN.sub("", value).strip()


# --- Build test template ---
# Purpose: Build a test recipe template from a base.
# Inputs: Base recipe and optional explicit test sequence number.
# Outputs: Unsaved Recipe model prefilled with branch/test metadata.
def build_test_template(base: Recipe, *, test_sequence: int | None = None) -> Recipe:
    test_name = base.name
    if not base.is_master and base.variation_name:
        test_name = base.variation_name
    if test_sequence:
        test_name = f"{test_name} - Test {test_sequence}"
    template = Recipe(
        name=test_name,
        instructions=base.instructions,
        label_prefix=base.label_prefix,
        predicted_yield=base.predicted_yield,
        predicted_yield_unit=base.predicted_yield_unit,
        category_id=base.category_id,
    )
    if test_sequence:
        template.test_sequence = test_sequence
    template.version_number = base.version_number
    template.recipe_group_id = base.recipe_group_id
    template.recipe_group = base.recipe_group
    template.is_master = base.is_master
    template.variation_name = base.variation_name
    template.variation_prefix = base.variation_prefix
    template.parent_recipe_id = base.id
    template.parent_master_id = base.parent_master_id
    template.parent_master = base.parent_master
    template.portioning_data = (
        base.portioning_data.copy()
        if isinstance(base.portioning_data, dict)
        else base.portioning_data
    )
    template.is_portioned = base.is_portioned
    template.portion_name = base.portion_name
    template.portion_count = base.portion_count
    template.portion_unit_id = base.portion_unit_id
    if base.category_data:
        template.category_data = (
            base.category_data.copy()
            if isinstance(base.category_data, dict)
            else base.category_data
        )
    template.skin_opt_in = base.skin_opt_in
    template.sharing_scope = "private"
    template.is_public = False
    template.is_for_sale = False
    return template


# --- Create test version ---
# Purpose: Create a test version from a base recipe.
# Inputs: Base recipe, request payload, and target lifecycle status.
# Outputs: Tuple indicating success and either created Recipe or error payload.
def create_test_version(
    base: Recipe, payload: Dict[str, Any], target_status: str
) -> Tuple[bool, Any]:
    next_test_sequence = _next_test_sequence(
        base.recipe_group_id,
        is_master=base.is_master,
        variation_name=base.variation_name,
    )
    base_name = base.name
    if not base.is_master and base.variation_name:
        base_name = base.variation_name
    test_name = f"{base_name} - Test {next_test_sequence}"
    test_payload = dict(payload)
    test_payload.update(
        {
            "name": test_name,
            "status": target_status,
            "is_test": True,
            "recipe_group_id": base.recipe_group_id,
            "variation_name": base.variation_name,
            "parent_master_id": base.parent_master_id,
            "parent_recipe_id": base.id,
            "root_recipe_id": base.root_recipe_id or base.id,
            "version_number_override": base.version_number,
            "test_sequence": next_test_sequence,
            "is_master_override": base.is_master,
            "sharing_scope": "private",
            "is_public": False,
            "is_for_sale": False,
            "marketplace_status": "draft",
        }
    )
    return create_recipe(**test_payload)


# --- Next test sequence ---
# Purpose: Expose next test sequence for a base recipe.
# Inputs: Base recipe used to resolve branch scope.
# Outputs: Integer test sequence number for the next test in branch.
def get_next_test_sequence(base: Recipe) -> int:
    return _next_test_sequence(
        base.recipe_group_id,
        is_master=base.is_master,
        variation_name=base.variation_name,
    )


# --- Promote test ---
# Purpose: Promote a test to the current version.
# Inputs: Recipe id for the test version being promoted.
# Outputs: Tuple indicating success and the promoted Recipe or an error message.
def promote_test_to_current(recipe_id: int) -> Tuple[bool, Any]:
    recipe = db.session.get(Recipe, recipe_id)
    if not recipe or recipe.test_sequence is None:
        return False, "Test version not found."

    parent_recipe = None
    if recipe.parent_recipe_id:
        parent_recipe = db.session.get(Recipe, recipe.parent_recipe_id)
    promoted_from_id = recipe.parent_recipe_id
    promoted_from_version = recipe.version_number
    promoted_from_test = recipe.test_sequence
    base_master_version = (
        recipe.parent_master.version_number if recipe.parent_master else None
    )

    base_query = Recipe.query.filter(
        Recipe.recipe_group_id == recipe.recipe_group_id,
        Recipe.is_master.is_(recipe.is_master),
        Recipe.test_sequence.is_(None),
    )
    if not recipe.is_master:
        normalized_variation_name = (recipe.variation_name or "").strip().lower()
        base_query = base_query.filter(
            sa.func.lower(Recipe.variation_name) == normalized_variation_name
        )
    max_version = (
        base_query.with_entities(sa.func.max(Recipe.version_number)).scalar() or 0
    )

    recipe.version_number = int(max_version) + 1
    recipe.test_sequence = None
    if recipe.is_master:
        restored_master_name = (
            (recipe.recipe_group.name if recipe.recipe_group else None)
            or (
                parent_recipe.recipe_group.name
                if parent_recipe and parent_recipe.recipe_group
                else None
            )
            or (parent_recipe.name if parent_recipe else None)
            or _strip_test_suffix(recipe.name)
        )
        if restored_master_name:
            recipe.name = restored_master_name
    else:
        restored_variation_name = (
            recipe.variation_name
            or (parent_recipe.variation_name if parent_recipe else None)
            or (parent_recipe.name if parent_recipe else None)
            or _strip_test_suffix(recipe.name)
        )
        if restored_variation_name:
            recipe.name = restored_variation_name
    if parent_recipe:
        if recipe.is_master:
            recipe.parent_recipe_id = None
        else:
            # Keep variation versions chained under the previous variation version.
            recipe.parent_recipe_id = parent_recipe.id
    recipe.status = "published"
    recipe.sharing_scope = "private"
    recipe.is_public = False
    recipe.is_for_sale = False
    recipe.sale_price = None
    recipe.marketplace_status = "draft"
    apply_current_flag(recipe)
    if promoted_from_test:
        if recipe.is_master:
            notes = f"Promoted from Master v{promoted_from_version} Test {promoted_from_test}"
        else:
            variation_label = recipe.variation_name or "Variation"
            if base_master_version:
                notes = (
                    f"Promoted from {variation_label} v{promoted_from_version} "
                    f"Test {promoted_from_test} (Base M{base_master_version})"
                )
            else:
                notes = (
                    f"Promoted from {variation_label} v{promoted_from_version} "
                    f"Test {promoted_from_test}"
                )
        _log_lineage_event(
            recipe,
            "PROMOTE_TEST",
            source_recipe_id=promoted_from_id,
            notes=notes,
        )
    db.session.commit()
    return True, recipe


# --- Unique recipe name ---
# Purpose: Generate a unique recipe name within an org.
# Inputs: Desired base recipe-group name and organization id.
# Outputs: Collision-safe name string for recipe-group creation flows.
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
        candidate = f"{base_name} ({suffix})"
    return candidate


# --- Promote to master ---
# Purpose: Promote a variation to master in the same group.
# Inputs: Variation recipe id that should be promoted into master branch.
# Outputs: Tuple indicating success and created master Recipe or error message.
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
        allow_duplicate_name_override=True,
        sharing_scope="private",
        is_public=False,
        is_for_sale=False,
        marketplace_status="draft",
    )


# --- Promote to new group ---
# Purpose: Promote a variation to a new recipe group.
# Inputs: Variation recipe id and optional override group name.
# Outputs: Tuple indicating success and created master Recipe or error message.
def promote_variation_to_new_group(
    recipe_id: int, group_name: str | None = None
) -> Tuple[bool, Any]:
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
    requested_name = (group_name or "").strip()
    if requested_name:
        candidate_name = requested_name
    else:
        candidate_name = _unique_recipe_name(
            recipe.name or "New Recipe Group", recipe.organization_id
        )

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
    "get_next_test_sequence",
    "promote_test_to_current",
    "promote_variation_to_master",
    "promote_variation_to_new_group",
]
