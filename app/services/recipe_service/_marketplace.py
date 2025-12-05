"""Marketplace helpers for recipes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from ...models import Recipe
from ._constants import _CENTS, _UNSET


def _normalize_sharing_scope(value: str | None) -> str:
    """Clamp sharing scope to supported values."""
    if not value:
        return 'private'
    normalized = str(value).strip().lower()
    if normalized in {'public', 'pub', 'shared'}:
        return 'public'
    return 'private'


def _default_marketplace_status(is_public: bool) -> str:
    return 'listed' if is_public else 'draft'


def _normalize_sale_price(value: Any) -> Optional[Decimal]:
    if value in (None, '', _UNSET):
        return None
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if price < 0:
        return None
    return price.quantize(_CENTS)


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
    original_scope = recipe.sharing_scope or 'private'
    resolved_scope = original_scope
    if sharing_scope is not None:
        resolved_scope = _normalize_sharing_scope(sharing_scope)
    if is_public is not None:
        resolved_scope = 'public' if is_public else 'private'
    scope_changed = resolved_scope != (recipe.sharing_scope or 'private')
    recipe.sharing_scope = resolved_scope
    recipe.is_public = resolved_scope == 'public'

    if is_for_sale is not None:
        recipe.is_for_sale = bool(is_for_sale) and recipe.is_public
    elif not recipe.is_public:
        recipe.is_for_sale = False

    if sale_price is not None or not recipe.is_for_sale:
        recipe.sale_price = _normalize_sale_price(sale_price) if recipe.is_for_sale else None

    if getattr(recipe, "is_resellable", True) is False:
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
        recipe.product_store_url = (product_store_url or '').strip() or None
    if skin_opt_in is not None:
        recipe.skin_opt_in = bool(skin_opt_in)

    if cover_image_path is not _UNSET:
        recipe.cover_image_path = cover_image_path
    if cover_image_url is not _UNSET:
        recipe.cover_image_url = cover_image_url
    if remove_cover_image:
        recipe.cover_image_path = None
        recipe.cover_image_url = None


__all__ = [
    "_apply_marketplace_settings",
]