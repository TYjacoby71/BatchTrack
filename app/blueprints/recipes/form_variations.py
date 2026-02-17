"""Recipe form variation helpers.

Synopsis:
Builds variation templates seeded from a parent recipe with version metadata.

Glossary:
- Variation template: Prefilled Recipe object for variation creation.
"""

from __future__ import annotations

from app.models import Recipe
from app.services.lineage_service import generate_variation_prefix


# --- Create variation template ---
# Purpose: Build a variation template from a parent recipe.
def create_variation_template(parent: Recipe) -> Recipe:
    variation_prefix = ""
    if parent.label_prefix:
        existing_variations = Recipe.query.filter(
            Recipe.parent_recipe_id == parent.id,
            Recipe.test_sequence.is_(None),
        ).count()
        variation_prefix = f"{parent.label_prefix}V{existing_variations + 1}"

    template = Recipe(
        name="Variation",
        instructions=parent.instructions,
        label_prefix=variation_prefix,
        parent_recipe_id=parent.id,
        predicted_yield=parent.predicted_yield,
        predicted_yield_unit=parent.predicted_yield_unit,
        category_id=parent.category_id,
    )
    template.recipe_group_id = parent.recipe_group_id
    template.recipe_group = parent.recipe_group
    template.version_number = 1
    template.is_master = False
    template.variation_name = "Variation"
    template.variation_prefix = generate_variation_prefix(
        template.variation_name,
        parent.recipe_group_id,
    )
    template.parent_master = parent

    template.allowed_containers = list(parent.allowed_containers or [])
    if getattr(parent, "org_origin_purchased", False):
        template.is_sellable = True
    else:
        template.is_sellable = getattr(parent, "is_sellable", True)

    if parent.portioning_data:
        template.portioning_data = (
            parent.portioning_data.copy()
            if isinstance(parent.portioning_data, dict)
            else parent.portioning_data
        )
    template.is_portioned = parent.is_portioned
    template.portion_name = parent.portion_name
    template.portion_count = parent.portion_count
    template.portion_unit_id = parent.portion_unit_id

    if parent.category_data:
        template.category_data = (
            parent.category_data.copy()
            if isinstance(parent.category_data, dict)
            else parent.category_data
        )
    # product_group_id has been removed from the system
    template.skin_opt_in = parent.skin_opt_in
    template.sharing_scope = "private"
    template.is_public = False
    template.is_for_sale = False

    template.product_store_url = parent.product_store_url

    return template


__all__ = ["create_variation_template"]
