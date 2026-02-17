"""Marketplace helpers for recipes.

Synopsis:
Normalizes marketplace fields and enforces listing rules.

Glossary:
- Sharing scope: Visibility rule for a recipe.
- Listing: Marketplace visibility for a recipe version.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from ...models import Recipe
from ._constants import _CENTS, _UNSET


# --- Normalize sharing scope ---
# Purpose: Normalize sharing scope input.
def _normalize_sharing_scope(value: str | None) -> str:
    """Clamp sharing scope to supported values."""
    if not value:
        return "private"
    normalized = str(value).strip().lower()
    if normalized in {"public", "pub", "shared"}:
        return "public"
    return "private"


# --- Default marketplace status ---
# Purpose: Choose default marketplace status.
def _default_marketplace_status(is_public: bool) -> str:
    return "listed" if is_public else "draft"


# --- Normalize sale price ---
# Purpose: Normalize sale price input.
def _normalize_sale_price(value: Any) -> Optional[Decimal]:
    if value in (None, "", _UNSET):
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if price < 0:
        return None
    return price.quantize(_CENTS)


# --- Apply marketplace rules ---
# Purpose: Apply marketplace rules to a recipe.
def _apply_marketplace_settings(
    recipe: Recipe,
    *,
    sharing_scope: str | None = None,
    is_public: bool | None = None,
    is_for_sale: bool = False,
    sale_price: Any = None,
    marketplace_status: str | None = None,
    marketplace_notes: str | None = None,
    public_description: str | None = None,
    product_store_url: str | None = None,
    skin_opt_in: bool | None = None,
    cover_image_path: Any = _UNSET,
    cover_image_url: Any = _UNSET,
    remove_cover_image: bool = False,
) -> None:
    target_scope = sharing_scope
    if target_scope is None and is_public is not None:
        target_scope = "public" if bool(is_public) else "private"
    if target_scope is None:
        target_scope = getattr(recipe, "sharing_scope", None)
    scope_value = _normalize_sharing_scope(target_scope)

    current_scope = getattr(recipe, "sharing_scope", None)
    scope_changed = (current_scope or "private") != scope_value
    recipe.sharing_scope = scope_value

    final_is_public = (
        bool(is_public) if is_public is not None else scope_value == "public"
    )
    recipe.is_public = final_is_public

    if is_for_sale is not None:
        recipe.is_for_sale = bool(is_for_sale) and recipe.is_public
    elif not recipe.is_public:
        recipe.is_for_sale = False

    if sale_price is not None or not recipe.is_for_sale:
        recipe.sale_price = (
            _normalize_sale_price(sale_price) if recipe.is_for_sale else None
        )

    if getattr(recipe, "is_sellable", True) is False:
        recipe.is_for_sale = False
        recipe.sale_price = None

    if marketplace_status:
        recipe.marketplace_status = marketplace_status
    elif scope_changed or not recipe.marketplace_status:
        recipe.marketplace_status = _default_marketplace_status(recipe.is_public)

    if marketplace_notes is not None:
        recipe.marketplace_notes = marketplace_notes

    if public_description is not None:
        recipe.public_description = public_description

    if product_store_url is not None:
        recipe.product_store_url = (product_store_url or "").strip() or None
    if skin_opt_in is not None:
        recipe.skin_opt_in = bool(skin_opt_in)

    if cover_image_path is not _UNSET:
        recipe.cover_image_path = cover_image_path
    if cover_image_url is not _UNSET:
        recipe.cover_image_url = cover_image_url
    if remove_cover_image:
        recipe.cover_image_path = None
        recipe.cover_image_url = None

    if (
        getattr(recipe, "status", None) != "published"
        or getattr(recipe, "test_sequence", None)
        or getattr(recipe, "is_archived", False)
        or not getattr(recipe, "is_current", False)
    ):
        recipe.sharing_scope = "private"
        recipe.is_public = False
        recipe.is_for_sale = False
        recipe.sale_price = None
        recipe.marketplace_status = "draft"
        return

    if recipe.is_public and recipe.marketplace_status == "listed":
        if not recipe.org_origin_purchased:
            recipe.org_origin_recipe_id = recipe.id
            if recipe.org_origin_type in (None, "authored"):
                recipe.org_origin_type = "published"

        if recipe.recipe_group_id:
            query = Recipe.query.filter(
                Recipe.recipe_group_id == recipe.recipe_group_id,
                Recipe.id != recipe.id,
                Recipe.test_sequence.is_(None),
            )
            if recipe.is_master:
                query = query.filter(Recipe.is_master.is_(True))
            else:
                query = query.filter(
                    Recipe.is_master.is_(False),
                    Recipe.variation_name == recipe.variation_name,
                )
            for other in query.all():
                other.is_public = False
                other.is_for_sale = False
                other.sale_price = None
                other.marketplace_status = "draft"


__all__ = [
    "_apply_marketplace_settings",
]
