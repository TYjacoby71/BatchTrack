from __future__ import annotations

from flask import has_app_context

from app.extensions import cache

__all__ = [
    "ingredient_list_cache_key",
    "invalidate_ingredient_list_cache",
    "product_list_cache_key",
    "invalidate_product_list_cache",
    "recipe_list_cache_key",
    "invalidate_recipe_list_cache",
]

_INGREDIENT_LIST_KEY = "bootstrap:ingredients:v1:{org_id}"
_RECIPE_LIST_KEY = "bootstrap:recipes:v1:{org_id}"
_PRODUCT_LIST_KEY = "bootstrap:products:v1:{org_id}:{sort}"
_PRODUCT_SORT_KEYS = ("name", "popular", "stock")


def _org_scope(org_id: int | None) -> str:
    return str(org_id or "anon")


def _safe_delete(key: str) -> None:
    if not key or not has_app_context():
        return
    try:
        cache.delete(key)
    except Exception:
        # Cache invalidation should never raise downstream.
        pass


def ingredient_list_cache_key(org_id: int | None) -> str:
    return _INGREDIENT_LIST_KEY.format(org_id=_org_scope(org_id))


def invalidate_ingredient_list_cache(org_id: int | None) -> None:
    _safe_delete(ingredient_list_cache_key(org_id))


def recipe_list_cache_key(org_id: int | None) -> str:
    return _RECIPE_LIST_KEY.format(org_id=_org_scope(org_id))


def invalidate_recipe_list_cache(org_id: int | None) -> None:
    _safe_delete(recipe_list_cache_key(org_id))


def product_list_cache_key(org_id: int | None, sort_key: str | None = None) -> str:
    normalized = (sort_key or "name").lower()
    return _PRODUCT_LIST_KEY.format(org_id=_org_scope(org_id), sort=normalized)


def invalidate_product_list_cache(org_id: int | None) -> None:
    for sort_key in _PRODUCT_SORT_KEYS:
        _safe_delete(product_list_cache_key(org_id, sort_key))
