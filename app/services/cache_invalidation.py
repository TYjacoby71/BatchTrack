from __future__ import annotations

from typing import Any, Mapping

from flask import has_app_context

from app.extensions import cache
from app.utils.cache_utils import stable_cache_key

__all__ = [
    "ingredient_list_cache_key",
    "invalidate_ingredient_list_cache",
    "product_list_cache_key",
    "product_bootstrap_cache_key",
    "invalidate_product_list_cache",
    "recipe_list_cache_key",
    "recipe_list_page_cache_key",
    "recipe_bootstrap_cache_key",
    "invalidate_recipe_list_cache",
    "global_library_cache_key",
    "invalidate_global_library_cache",
    "recipe_library_cache_key",
    "invalidate_public_recipe_library_cache",
    "inventory_list_cache_key",
    "invalidate_inventory_list_cache",
]

_INGREDIENT_LIST_KEY = "bootstrap:ingredients:v1:{org_id}"
_RECIPE_LIST_KEY = "bootstrap:recipes:v1:{org_id}"
_RECIPE_PAGE_KEY = "bootstrap:recipes:page:v1:{org_id}"
_RECIPE_BOOTSTRAP_KEY = "bootstrap_api:recipes:v1:{org_id}"
_PRODUCT_LIST_KEY = "bootstrap:products:v1:{org_id}:{sort}"
_PRODUCT_BOOTSTRAP_KEY = "bootstrap_api:products:v1:{org_id}"
_PRODUCT_SORT_KEYS = ("name", "popular", "stock")
_GLOBAL_LIBRARY_NAMESPACE = "global_library_cache"
_RECIPE_LIBRARY_NAMESPACE = "recipe_library_public_cache"
_INVENTORY_LIST_NAMESPACE = "inventory_list_cache"


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


def recipe_list_page_cache_key(org_id: int | None) -> str:
    return _RECIPE_PAGE_KEY.format(org_id=_org_scope(org_id))


def recipe_bootstrap_cache_key(org_id: int | None) -> str:
    return _RECIPE_BOOTSTRAP_KEY.format(org_id=_org_scope(org_id))


def invalidate_recipe_list_cache(org_id: int | None) -> None:
    _safe_delete(recipe_list_cache_key(org_id))
    _safe_delete(recipe_list_page_cache_key(org_id))
    _safe_delete(recipe_bootstrap_cache_key(org_id))


def product_list_cache_key(org_id: int | None, sort_key: str | None = None) -> str:
    normalized = (sort_key or "name").lower()
    return _PRODUCT_LIST_KEY.format(org_id=_org_scope(org_id), sort=normalized)


def product_bootstrap_cache_key(org_id: int | None) -> str:
    return _PRODUCT_BOOTSTRAP_KEY.format(org_id=_org_scope(org_id))


def invalidate_product_list_cache(org_id: int | None) -> None:
    for sort_key in _PRODUCT_SORT_KEYS:
        _safe_delete(product_list_cache_key(org_id, sort_key))
    _safe_delete(product_bootstrap_cache_key(org_id))


def _namespace_version(namespace: str) -> int:
    if not has_app_context():
        return 1
    version_key = f"{namespace}:__version__"
    try:
        version = cache.get(version_key)
    except Exception:
        version = None
    if not version:
        version = 1
        try:
            cache.set(version_key, version)
        except Exception:
            pass
    return int(version or 1)


def _versioned_key(namespace: str, raw_key: str) -> str:
    version = _namespace_version(namespace)
    return f"{namespace}:v{version}:{raw_key}"


def _bump_namespace(namespace: str) -> None:
    if not has_app_context():
        return
    version_key = f"{namespace}:__version__"
    try:
        version = int(cache.get(version_key) or 1) + 1
    except Exception:
        version = 2
    try:
        cache.set(version_key, version)
    except Exception:
        pass


def global_library_cache_key(raw_key: str) -> str:
    return _versioned_key(_GLOBAL_LIBRARY_NAMESPACE, raw_key)


def invalidate_global_library_cache() -> None:
    _bump_namespace(_GLOBAL_LIBRARY_NAMESPACE)


def recipe_library_cache_key(raw_key: str) -> str:
    return _versioned_key(_RECIPE_LIBRARY_NAMESPACE, raw_key)


def invalidate_public_recipe_library_cache() -> None:
    _bump_namespace(_RECIPE_LIBRARY_NAMESPACE)


def _inventory_namespace(org_id: int | None) -> str:
    return f"{_INVENTORY_LIST_NAMESPACE}:{_org_scope(org_id)}"


def inventory_list_cache_key(org_id: int | None, params: Mapping[str, Any] | None = None) -> str:
    """
    Produce a namespaced cache key for inventory list payloads using request filters.
    """
    payload: dict[str, Any] = {"org": _org_scope(org_id)}
    if params:
        for key in sorted(params.keys()):
            payload[key] = params[key]
    digest = stable_cache_key("inventory:list", payload)
    return _versioned_key(_inventory_namespace(org_id), digest)


def invalidate_inventory_list_cache(org_id: int | None) -> None:
    _bump_namespace(_inventory_namespace(org_id))
