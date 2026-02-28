from __future__ import annotations
import logging

from collections import OrderedDict
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import GlobalItem
from app.models.category import IngredientCategory

logger = logging.getLogger(__name__)


DEFAULT_SCOPE = "ingredient"
VALID_SCOPES = ("ingredient", "container", "packaging", "consumable")
DEFAULT_PER_PAGE_OPTIONS = (10, 50, 100)
SCOPE_LABELS = OrderedDict(
    [
        ("ingredient", "Ingredients"),
        ("container", "Containers"),
        ("packaging", "Packaging"),
        ("consumable", "Consumables"),
    ]
)


def _resolve_scope(candidate: Optional[str]) -> str:
    scope = (candidate or DEFAULT_SCOPE).lower()
    if scope not in VALID_SCOPES:
        return DEFAULT_SCOPE
    return scope


def _resolve_page_args(
    page: Optional[int],
    per_page: Optional[int],
    per_page_options: tuple[int, ...] = DEFAULT_PER_PAGE_OPTIONS,
) -> tuple[int, int]:
    safe_page = page or 1
    if safe_page < 1:
        safe_page = 1
    safe_per_page = per_page or per_page_options[0]
    if safe_per_page not in per_page_options:
        safe_per_page = per_page_options[0]
    return safe_page, safe_per_page


def _attach_search_filter(query, search_query: str):
    if not search_query:
        return query

    term = f"%{search_query}%"
    alias_table = None
    try:
        alias_table = db.Table(
            "global_item_alias", db.metadata, autoload_with=db.engine
        )
    except Exception:  # pragma: no cover - defensive
        logger.warning("Suppressed exception fallback at app/services/global_item_listing_service.py:57", exc_info=True)
        alias_table = None

    if alias_table is None:
        return query.filter(GlobalItem.name.ilike(term))

    return query.filter(
        or_(
            GlobalItem.name.ilike(term),
            exists().where(
                and_(
                    alias_table.c.global_item_id == GlobalItem.id,
                    alias_table.c.alias.ilike(term),
                )
            ),
        )
    )


def _fetch_categories() -> List[str]:
    try:
        rows = (
            db.session.query(IngredientCategory.name)
            .join(
                GlobalItem, GlobalItem.ingredient_category_id == IngredientCategory.id
            )
            .filter(
                IngredientCategory.organization_id.is_(None),
                IngredientCategory.is_global_category.is_(True),
                GlobalItem.item_type == "ingredient",
                not GlobalItem.is_archived,
            )
            .distinct()
            .order_by(IngredientCategory.name.asc())
            .all()
        )
        categories = [row[0] for row in rows if row and row[0]]
        if categories:
            return categories
    except Exception:  # pragma: no cover - defensive
        logger.warning("Suppressed exception fallback at app/services/global_item_listing_service.py:96", exc_info=True)
        pass

    fallback = (
        IngredientCategory.query.filter_by(
            organization_id=None,
            is_active=True,
            is_global_category=True,
        )
        .order_by(IngredientCategory.name.asc())
        .all()
    )
    return [cat.name for cat in fallback if getattr(cat, "name", None)]


def _group_items(items: List[GlobalItem]) -> List[Dict[str, Any]]:
    buckets = OrderedDict()
    for gi in items:
        key = gi.ingredient_id or f"item-{gi.id}"
        bucket = buckets.setdefault(
            key,
            {
                "ingredient": getattr(gi, "ingredient", None),
                "items": [],
            },
        )
        bucket["items"].append(gi)
    return list(buckets.values())


def fetch_global_item_listing(
    *,
    scope: Optional[str] = None,
    search_query: str = "",
    category_filter: str = "",
    page: Optional[int] = None,
    per_page: Optional[int] = None,
    per_page_options: tuple[int, ...] = DEFAULT_PER_PAGE_OPTIONS,
) -> Dict[str, Any]:
    """Centralized query + pagination helper for the global library listings."""

    normalized_scope = _resolve_scope(scope)
    safe_page, safe_per_page = _resolve_page_args(page, per_page, per_page_options)

    query = GlobalItem.query.filter(
        not GlobalItem.is_archived,
        GlobalItem.item_type == normalized_scope,
    )

    if normalized_scope == "ingredient" and category_filter:
        query = query.join(
            IngredientCategory,
            GlobalItem.ingredient_category_id == IngredientCategory.id,
        ).filter(IngredientCategory.name == category_filter)

    if search_query:
        query = _attach_search_filter(query, search_query)

    eager_options = [
        joinedload(GlobalItem.ingredient_category),
    ]
    if normalized_scope == "ingredient":
        eager_options.extend(
            [
                joinedload(GlobalItem.ingredient),
                joinedload(GlobalItem.variation),
            ]
        )

    query = query.options(*eager_options)

    if normalized_scope == "ingredient":
        order_by = [GlobalItem.ingredient_id.asc(), GlobalItem.name.asc()]
    else:
        order_by = [GlobalItem.name.asc()]

    pagination = query.order_by(*order_by).paginate(
        page=safe_page, per_page=safe_per_page, error_out=False
    )
    items = pagination.items
    grouped_items = _group_items(items) if normalized_scope == "ingredient" else []

    categories = _fetch_categories() if normalized_scope == "ingredient" else []

    if pagination.total:
        first_index = ((pagination.page - 1) * pagination.per_page) + 1
        last_index = min(pagination.page * pagination.per_page, pagination.total)
    else:
        first_index = 0
        last_index = 0

    return {
        "scope": normalized_scope,
        "items": items,
        "grouped_items": grouped_items,
        "categories": categories,
        "pagination": pagination,
        "first_item_index": first_index,
        "last_item_index": last_index,
        "per_page": safe_per_page,
        "per_page_options": per_page_options,
    }
