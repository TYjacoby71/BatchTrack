"""Organization origin helpers for recipes."""

from __future__ import annotations
import logging

from typing import Any, Dict, Optional

from flask import current_app

from ...models import Recipe

logger = logging.getLogger(__name__)



def _get_batchtrack_org_id() -> int:
    try:
        return int(current_app.config.get("BATCHTRACK_ORG_ID", 1))
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/recipe_service/_origin.py:15", exc_info=True)
        return 1


def _default_org_origin_type(org_id: Optional[int]) -> str:
    if org_id and org_id == _get_batchtrack_org_id():
        return "batchtrack_native"
    return "authored"


def _build_org_origin_context(
    target_org_id: Optional[int],
    parent_recipe: Optional[Recipe],
    clone_source: Optional[Recipe],
) -> Dict[str, Any]:
    context = {
        "org_origin_type": _default_org_origin_type(target_org_id),
        "org_origin_source_org_id": None,
        "org_origin_source_recipe_id": None,
        "org_origin_purchased": False,
        "org_origin_recipe_id": None,
    }

    if parent_recipe and parent_recipe.organization_id == target_org_id:
        context["org_origin_recipe_id"] = (
            parent_recipe.org_origin_recipe_id or parent_recipe.id
        )
        context["org_origin_type"] = (
            parent_recipe.org_origin_type or context["org_origin_type"]
        )
        context["org_origin_source_org_id"] = parent_recipe.org_origin_source_org_id
        context["org_origin_source_recipe_id"] = (
            parent_recipe.org_origin_source_recipe_id
        )
        context["org_origin_purchased"] = parent_recipe.org_origin_purchased or False
        return context

    if clone_source and clone_source.organization_id == target_org_id:
        context["org_origin_recipe_id"] = (
            clone_source.org_origin_recipe_id or clone_source.id
        )
        context["org_origin_type"] = (
            clone_source.org_origin_type or context["org_origin_type"]
        )
        context["org_origin_source_org_id"] = clone_source.org_origin_source_org_id
        context["org_origin_source_recipe_id"] = (
            clone_source.org_origin_source_recipe_id
        )
        context["org_origin_purchased"] = clone_source.org_origin_purchased or False
        return context

    source = parent_recipe or clone_source
    if source and source.organization_id and source.organization_id != target_org_id:
        context["org_origin_type"] = "purchased"
        context["org_origin_purchased"] = True
        context["org_origin_source_org_id"] = source.organization_id
        context["org_origin_source_recipe_id"] = source.root_recipe_id or source.id

    return context


def _resolve_is_sellable(
    *,
    explicit_flag: bool | None,
    recipe_org_id: Optional[int],
    parent_recipe: Optional[Recipe],
    clone_source: Optional[Recipe],
    origin_context: Dict[str, Any],
) -> bool:
    """Determine whether a newly created recipe may be offered for sale."""
    if explicit_flag is not None:
        return bool(explicit_flag)

    if origin_context.get("org_origin_purchased"):
        return False

    if (
        clone_source
        and clone_source.organization_id
        and recipe_org_id
        and clone_source.organization_id != recipe_org_id
    ):
        return False

    if clone_source and getattr(clone_source, "is_sellable", True) is False:
        return False

    if parent_recipe and getattr(parent_recipe, "is_sellable", True) is False:
        return False

    return True


__all__ = [
    "_build_org_origin_context",
    "_resolve_is_sellable",
]
