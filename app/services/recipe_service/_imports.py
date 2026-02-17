"""Inventory import helpers supporting recipe duplication."""

from __future__ import annotations

import logging
import re
from typing import Optional

from flask_login import current_user

from ...extensions import db
from ...models import InventoryItem
from ...models.global_item import GlobalItem
from ..inventory_adjustment._creation_logic import create_inventory_item

logger = logging.getLogger(__name__)

_WORD_SANITIZE_RE = re.compile(r"[^a-z0-9\s]+")


def _resolve_import_name(
    fallback_name: Optional[str], global_item_id: Optional[int]
) -> str:
    name = (fallback_name or "").strip()
    if name:
        return name
    if global_item_id:
        try:
            global_item = db.session.get(GlobalItem, int(global_item_id))
            if global_item and getattr(global_item, "name", None):
                return global_item.name
        except Exception:
            pass
    return "Imported Item"


def _singularize_token(token: str) -> str:
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith(("ses", "xes", "zes", "ches", "shes")):
        return token[:-2]
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _normalize_item_name_for_match(name: Optional[str]) -> str:
    if not name:
        return ""
    cleaned = _WORD_SANITIZE_RE.sub(" ", name.lower()).strip()
    if not cleaned:
        return ""
    tokens = [token for token in cleaned.split() if token]
    normalized_tokens = [_singularize_token(token) for token in tokens]
    return " ".join(normalized_tokens)


def _resolve_import_unit(
    fallback_unit: Optional[str],
    fallback_type: Optional[str],
    global_item: Optional[GlobalItem],
) -> str:
    if fallback_unit:
        return fallback_unit
    if global_item and getattr(global_item, "default_unit", None):
        return global_item.default_unit
    if (fallback_type or "").lower() == "container":
        return "count"
    return "gram"


def _match_inventory_item_by_normalized_name(
    organization_id: int,
    normalized_name: str,
    item_type: Optional[str],
) -> Optional[InventoryItem]:
    query = InventoryItem.query.filter(InventoryItem.organization_id == organization_id)
    if item_type:
        query = query.filter(InventoryItem.type == item_type)

    candidates = query.with_entities(InventoryItem.id, InventoryItem.name).all()
    for candidate_id, candidate_name in candidates:
        if _normalize_item_name_for_match(candidate_name) == normalized_name:
            return db.session.get(InventoryItem, candidate_id)
    return None


def _ensure_inventory_item_for_import(
    *,
    organization_id: Optional[int],
    global_item_id: Optional[int],
    fallback_name: Optional[str],
    fallback_unit: Optional[str],
    fallback_type: Optional[str],
) -> Optional[int]:
    if not organization_id:
        return None

    if global_item_id:
        existing = (
            InventoryItem.query.filter(
                InventoryItem.organization_id == organization_id,
                InventoryItem.global_item_id == global_item_id,
            )
            .order_by(InventoryItem.id.asc())
            .first()
        )
        if existing:
            return existing.id

    global_item = None
    if global_item_id:
        try:
            global_item = db.session.get(GlobalItem, int(global_item_id))
        except Exception:
            global_item = None

    display_name = _resolve_import_name(
        fallback_name,
        global_item_id if global_item_id else None,
    )
    normalized_match_key = _normalize_item_name_for_match(display_name)
    normalized_type = fallback_type or (
        global_item.item_type if global_item else "ingredient"
    )
    normalized_unit = _resolve_import_unit(fallback_unit, normalized_type, global_item)

    if not global_item_id and normalized_match_key:
        name_match = _match_inventory_item_by_normalized_name(
            organization_id,
            normalized_match_key,
            normalized_type,
        )
        if name_match:
            return name_match.id

    form_payload = {
        "name": display_name,
        "unit": normalized_unit,
        "type": normalized_type,
    }
    if global_item_id:
        form_payload["global_item_id"] = global_item_id

    success, message, item_id = create_inventory_item(
        form_payload,
        organization_id=organization_id,
        created_by=getattr(current_user, "id", None),
    )
    if not success:
        logger.warning(
            "Unable to auto-create inventory item during import: %s", message
        )
        return None
    return item_id


__all__ = [
    "_ensure_inventory_item_for_import",
]
