"""Recipe form parsing utilities.

Synopsis:
Parses recipe form submissions into service payloads. Handles ingredient extraction,
portioning metadata, and marketplace payload normalization.

Glossary:
- Submission: Parsed form data ready for service calls.
- Portioning: Portion-specific yield metadata derived from the form.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from flask_login import current_user
from sqlalchemy import func

from app.extensions import db
from app.models import GlobalItem, InventoryItem, Recipe
from app.models.unit import Unit
from app.services.inventory_adjustment import create_inventory_item
from app.services.recipe_marketplace_service import RecipeMarketplaceService

from .form_prefill import safe_int
from .form_templates import is_recipe_purchase_enabled, is_recipe_sharing_enabled

logger = logging.getLogger(__name__)


@dataclass
# --- RecipeFormSubmission ---
# Purpose: Capture parsed form submission payloads for service calls.
class RecipeFormSubmission:
    kwargs: Dict[str, Any]
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


# --- Build recipe submission ---
# Purpose: Parse recipe form data into a submission object.
def build_recipe_submission(
    form,
    files,
    *,
    defaults: Optional[Recipe] = None,
    existing: Optional[Recipe] = None,
) -> RecipeFormSubmission:
    ingredients = extract_ingredients_from_form(form)
    consumables = extract_consumables_from_form(form)
    allowed_containers = collect_allowed_containers(form)

    portion_payload, portion_fields = parse_portioning_from_form(form)
    category_id = safe_int(form.get("category_id"))

    fallback_yield = getattr(defaults, "predicted_yield", None)
    if fallback_yield is None:
        fallback_yield = 0.0
    yield_amount = coerce_float(form.get("predicted_yield"), fallback=fallback_yield)
    fallback_unit = getattr(defaults, "predicted_yield_unit", "") if defaults else ""
    yield_unit = form.get("predicted_yield_unit") or fallback_unit or ""

    marketplace_ok, marketplace_result = RecipeMarketplaceService.extract_submission(
        form, files, existing=existing
    )
    if not marketplace_ok:
        return RecipeFormSubmission({}, marketplace_result)
    marketplace_payload, cover_payload = _sanitize_marketplace_submission(
        marketplace_result.get("marketplace", {}),
        marketplace_result.get("cover", {}),
        existing=existing,
        sharing_enabled=is_recipe_sharing_enabled(),
        purchase_enabled=is_recipe_purchase_enabled(),
    )

    kwargs: Dict[str, Any] = {
        "name": form.get("name"),
        "description": form.get("instructions"),
        "instructions": form.get("instructions"),
        "yield_amount": yield_amount,
        "yield_unit": yield_unit,
        "ingredients": ingredients,
        "consumables": consumables,
        "allowed_containers": allowed_containers,
        "label_prefix": form.get("label_prefix"),
        "category_id": category_id,
        "portioning_data": portion_payload,
        "is_portioned": portion_fields["is_portioned"],
        "portion_name": portion_fields["portion_name"],
        "portion_count": portion_fields["portion_count"],
        "portion_unit_id": portion_fields["portion_unit_id"],
    }
    kwargs.update(marketplace_payload)
    kwargs.update(cover_payload)

    return RecipeFormSubmission(kwargs)


# --- Collect allowed containers ---
# Purpose: Extract allowed container ids from form data.
def collect_allowed_containers(form) -> list[int]:
    containers: list[int] = []
    for raw in form.getlist("allowed_containers[]"):
        value = safe_int(raw)
        if value:
            containers.append(value)
    return containers


# --- Parse portioning ---
# Purpose: Extract portioning metadata and validation errors.
def parse_portioning_from_form(form) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    truthy = {"true", "1", "yes", "on"}
    flag = str(form.get("is_portioned") or "").strip().lower() in truthy
    default_fields = {
        "is_portioned": False,
        "portion_name": None,
        "portion_count": None,
        "portion_unit_id": None,
    }
    if not flag:
        return None, default_fields

    portion_name = (form.get("portion_name") or "").strip() or None
    portion_count = safe_int(form.get("portion_count"))
    portion_unit_id = ensure_portion_unit(portion_name)

    payload = {
        "is_portioned": True,
        "portion_name": portion_name,
        "portion_count": portion_count,
        "portion_unit_id": portion_unit_id,
    }
    return payload, payload.copy()


# --- Ensure portion unit ---
# Purpose: Ensure a portion unit exists for portioning forms.
def ensure_portion_unit(portion_name: Optional[str]) -> Optional[int]:
    if not portion_name:
        return None

    try:
        existing = (
            Unit.query.filter(Unit.name == portion_name)
            .order_by((Unit.organization_id == current_user.organization_id).desc())
            .first()
        )
    except Exception:
        existing = None

    if existing:
        return existing.id

    if not getattr(current_user, "is_authenticated", False):
        return None

    try:
        unit = Unit(
            name=portion_name,
            unit_type="count",
            base_unit="count",
            conversion_factor=1.0,
            is_active=True,
            is_custom=True,
            is_mapped=False,
            organization_id=current_user.organization_id,
            created_by=current_user.id,
        )
        db.session.add(unit)
        db.session.flush()
        return unit.id
    except Exception:
        db.session.rollback()
        return None


# --- Coerce float ---
# Purpose: Safely coerce values to float with fallback.
def coerce_float(value: Any, *, fallback: float = 0.0) -> float:
    if value in (None, ""):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


# --- Extract ingredients ---
# Purpose: Parse ingredient rows from the recipe form.
def extract_ingredients_from_form(form):
    ingredients = []
    ingredient_ids = form.getlist("ingredient_ids[]")
    global_item_ids = form.getlist("global_item_ids[]")
    amounts = form.getlist("amounts[]")
    units = form.getlist("units[]")

    max_len = max(len(ingredient_ids), len(global_item_ids), len(amounts), len(units))
    ingredient_ids += [""] * (max_len - len(ingredient_ids))
    global_item_ids += [""] * (max_len - len(global_item_ids))
    amounts += [""] * (max_len - len(amounts))
    units += [""] * (max_len - len(units))

    for ing_id, gi_id, amt, unit in zip(
        ingredient_ids, global_item_ids, amounts, units
    ):
        if not amt or not unit:
            continue

        try:
            quantity = float(str(amt).strip())
        except (ValueError, TypeError):
            logger.error("Invalid quantity provided for ingredient line: %s", amt)
            continue

        item_id = None
        if ing_id:
            try:
                item_id = int(ing_id)
            except (ValueError, TypeError):
                item_id = None

        if not item_id and gi_id:
            try:
                gi = db.session.get(GlobalItem, int(gi_id)) if gi_id else None
            except Exception:
                gi = None

            if gi:
                try:
                    existing = (
                        InventoryItem.scoped().filter_by(
                            organization_id=current_user.organization_id,
                            global_item_id=gi.id,
                            type=gi.item_type,
                        )
                        .order_by(InventoryItem.id.asc())
                        .first()
                    )
                except Exception:
                    existing = None

                if existing:
                    item_id = int(existing.id)
                else:
                    try:
                        name_match = (
                            InventoryItem.scoped().filter(
                                InventoryItem.organization_id
                                == current_user.organization_id,
                                func.lower(InventoryItem.name)
                                == func.lower(db.literal(gi.name)),
                                InventoryItem.type == gi.item_type,
                            )
                            .order_by(InventoryItem.id.asc())
                            .first()
                        )
                    except Exception:
                        name_match = None

                    if name_match:
                        try:
                            name_match.global_item_id = gi.id
                            name_match.ownership = "global"
                            db.session.flush()
                        except Exception:
                            db.session.rollback()
                        item_id = int(name_match.id)
                    else:
                        form_like = {
                            "name": gi.name,
                            "type": gi.item_type,
                            "unit": gi.default_unit or "",
                            "global_item_id": gi.id,
                        }

                        success, message, created_id = create_inventory_item(
                            form_data=form_like,
                            organization_id=current_user.organization_id,
                            created_by=current_user.id,
                        )
                        if not success:
                            logger.error(
                                "Failed to auto-create inventory for global item %s: %s",
                                gi.id,
                                message,
                            )
                        else:
                            item_id = int(created_id)
            else:
                logger.error("Global item not found for id %s", gi_id)

        if item_id:
            ingredients.append(
                {
                    "item_id": item_id,
                    "quantity": quantity,
                    "unit": (unit or "").strip(),
                }
            )

    return ingredients


# --- Extract consumables ---
# Purpose: Parse consumable rows from the recipe form.
def extract_consumables_from_form(form):
    consumables = []
    ids = form.getlist("consumable_ids[]")
    amounts = form.getlist("consumable_amounts[]")
    units = form.getlist("consumable_units[]")
    for item_id, amt, unit in zip(ids, amounts, units):
        if item_id and amt and unit:
            try:
                consumables.append(
                    {
                        "item_id": int(item_id),
                        "quantity": float(amt.strip()),
                        "unit": unit.strip(),
                    }
                )
            except (ValueError, TypeError) as exc:
                logger.error("Invalid consumable data: %s", exc)
                continue
    return consumables


# --- Get submission status ---
# Purpose: Determine the desired recipe status from form input.
def get_submission_status(form):
    mode = (form.get("save_mode") or "").strip().lower()
    return "draft" if mode == "draft" else "published"


# --- Parse service error ---
# Purpose: Normalize service exceptions into display messages.
def parse_service_error(error):
    if isinstance(error, dict):
        message = error.get("error") or error.get("message") or "An error occurred"
        missing_fields = error.get("missing_fields") or []
        return message, missing_fields
    return str(error), []


# --- Build draft prompt ---
# Purpose: Build user-facing messages for draft prompts.
def build_draft_prompt(missing_fields, attempted_status, message):
    if missing_fields and attempted_status != "draft":
        return {"missing_fields": missing_fields, "message": message}
    return None


# --- Sanitize marketplace submission ---
# Purpose: Clean marketplace-specific fields for recipes.
def _sanitize_marketplace_submission(
    marketplace_payload: Dict[str, Any],
    cover_payload: Dict[str, Any],
    *,
    existing: Optional[Recipe] = None,
    sharing_enabled: bool,
    purchase_enabled: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if not sharing_enabled:
        return _marketplace_payload_from_existing(existing), {}

    sanitized = dict(marketplace_payload or {})
    if not purchase_enabled:
        sanitized["is_for_sale"] = False
        sanitized["sale_price"] = None
        sanitized["product_store_url"] = None
    return sanitized, cover_payload


# --- Marketplace payload ---
# Purpose: Build marketplace payloads from existing recipes.
def _marketplace_payload_from_existing(existing: Optional[Recipe]) -> Dict[str, Any]:
    if not existing:
        return {
            "sharing_scope": "private",
            "is_public": False,
            "is_for_sale": False,
            "sale_price": None,
            "product_store_url": None,
            "marketplace_notes": None,
            "public_description": None,
            "skin_opt_in": True,
        }
    return {
        "sharing_scope": "public" if existing.is_public else "private",
        "is_public": bool(existing.is_public),
        "is_for_sale": bool(existing.is_for_sale),
        "sale_price": existing.sale_price,
        "product_store_url": existing.product_store_url,
        "marketplace_notes": existing.marketplace_notes,
        "public_description": existing.public_description,
        "skin_opt_in": (
            bool(existing.skin_opt_in) if existing.skin_opt_in is not None else True
        ),
    }


__all__ = [
    "RecipeFormSubmission",
    "build_recipe_submission",
    "build_draft_prompt",
    "collect_allowed_containers",
    "coerce_float",
    "ensure_portion_unit",
    "extract_consumables_from_form",
    "extract_ingredients_from_form",
    "get_submission_status",
    "parse_portioning_from_form",
    "parse_service_error",
]
