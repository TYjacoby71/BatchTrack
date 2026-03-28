"""Public catalog service boundary.

Synopsis:
Owns public unit listing and global-item search query/payload shaping so
`api/public.py` routes remain transport-focused.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

from sqlalchemy import func, or_

from app.extensions import db
from app.models.global_item import GlobalItem
from app.models.models import Unit

logger = logging.getLogger(__name__)


class PublicCatalogService:
    """Service helpers for unauthenticated public catalog endpoints."""

    @staticmethod
    def list_public_units() -> list[dict[str, Any]]:
        units = (
            Unit.query.filter_by(is_active=True, is_custom=False)
            .order_by(Unit.unit_type.asc(), Unit.name.asc())
            .all()
        )
        return [
            {
                "id": unit.id,
                "name": unit.name,
                "symbol": getattr(unit, "symbol", None),
                "unit_type": unit.unit_type,
            }
            for unit in units
        ]

    @staticmethod
    def search_global_items(
        *,
        query_text: str,
        item_type: str | None,
        group_mode: bool,
        limit: int = 25,
    ) -> dict[str, Any]:
        if not query_text:
            return {"success": True, "results": []}

        query = GlobalItem.query.filter(GlobalItem.is_archived.is_(False))
        if item_type:
            query = query.filter(GlobalItem.item_type == item_type)

        term = f"%{query_text}%"
        try:
            alias_table = db.Table(
                "global_item_alias",
                db.metadata,
                autoload_with=db.engine,
            )
            query = query.filter(
                or_(
                    GlobalItem.name.ilike(term),
                    db.exists()
                    .where(alias_table.c.global_item_id == GlobalItem.id)
                    .where(alias_table.c.alias.ilike(term)),
                )
            )
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/public_catalog_service.py:58",
                exc_info=True,
            )
            query = query.filter(GlobalItem.name.ilike(term))

        items = query.order_by(func.length(GlobalItem.name).asc()).limit(limit).all()
        grouped = OrderedDict() if group_mode else None
        results: list[dict[str, Any]] = []

        for global_item in items:
            ingredient_obj = (
                global_item.ingredient
                if getattr(global_item, "ingredient", None)
                else None
            )
            ingredient_category_obj = (
                ingredient_obj.category
                if ingredient_obj and getattr(ingredient_obj, "category", None)
                else None
            )
            variation_obj = (
                global_item.variation
                if getattr(global_item, "variation", None)
                else None
            )
            physical_form_obj = (
                variation_obj.physical_form
                if variation_obj and getattr(variation_obj, "physical_form", None)
                else (
                    global_item.physical_form
                    if getattr(global_item, "physical_form", None)
                    else None
                )
            )

            ingredient_payload = None
            if ingredient_obj:
                ingredient_payload = {
                    "id": ingredient_obj.id,
                    "name": ingredient_obj.name,
                    "slug": ingredient_obj.slug,
                    "inci_name": ingredient_obj.inci_name,
                    "cas_number": ingredient_obj.cas_number,
                    "ingredient_category_id": ingredient_obj.ingredient_category_id,
                    "ingredient_category_name": (
                        ingredient_category_obj.name
                        if ingredient_category_obj
                        else None
                    ),
                }

            variation_payload = None
            if variation_obj:
                variation_payload = {
                    "id": variation_obj.id,
                    "name": variation_obj.name,
                    "slug": variation_obj.slug,
                    "default_unit": variation_obj.default_unit,
                    "form_bypass": variation_obj.form_bypass,
                    "physical_form_id": variation_obj.physical_form_id,
                    "physical_form_name": (
                        physical_form_obj.name if physical_form_obj else None
                    ),
                }

            physical_form_payload = None
            if physical_form_obj:
                physical_form_payload = {
                    "id": physical_form_obj.id,
                    "name": physical_form_obj.name,
                    "slug": physical_form_obj.slug,
                }

            function_names = [
                tag.name for tag in getattr(global_item, "functions", []) or []
            ]
            application_names = [
                tag.name for tag in getattr(global_item, "applications", []) or []
            ]
            category_tag_names = [
                tag.name for tag in getattr(global_item, "category_tags", []) or []
            ]

            display_name = PublicCatalogService._display_name(
                fallback_name=global_item.name,
                ingredient_payload=ingredient_payload,
                variation_payload=variation_payload,
                physical_form_payload=physical_form_payload,
            )

            item_payload = {
                "id": global_item.id,
                "name": display_name,
                "text": display_name,
                "display_name": display_name,
                "raw_name": global_item.name,
                "item_type": global_item.item_type,
                "ingredient": ingredient_payload,
                "variation": variation_payload,
                "variation_id": variation_payload["id"] if variation_payload else None,
                "variation_name": (
                    variation_payload["name"] if variation_payload else None
                ),
                "variation_slug": (
                    variation_payload["slug"] if variation_payload else None
                ),
                "physical_form": physical_form_payload,
                "functions": function_names,
                "applications": application_names,
                "default_unit": global_item.default_unit,
                "unit": global_item.default_unit,
                "density": global_item.density,
                "default_is_perishable": global_item.default_is_perishable,
                "recommended_shelf_life_days": global_item.recommended_shelf_life_days,
                "saponification_value": getattr(
                    global_item, "saponification_value", None
                ),
                "iodine_value": getattr(global_item, "iodine_value", None),
                "fatty_acid_profile": getattr(global_item, "fatty_acid_profile", None),
                "melting_point_c": getattr(global_item, "melting_point_c", None),
                "recommended_fragrance_load_pct": (
                    global_item.recommended_fragrance_load_pct
                ),
                "is_active_ingredient": global_item.is_active_ingredient,
                "inci_name": global_item.inci_name,
                "cas_number": getattr(global_item, "cas_number", None),
                "protein_content_pct": global_item.protein_content_pct,
                "brewing_color_srm": global_item.brewing_color_srm,
                "brewing_potential_sg": global_item.brewing_potential_sg,
                "brewing_diastatic_power_lintner": (
                    global_item.brewing_diastatic_power_lintner
                ),
                "certifications": global_item.certifications or [],
                "category_tags": category_tag_names,
                "ingredient_name": (
                    ingredient_payload["name"] if ingredient_payload else None
                ),
                "physical_form_name": (
                    physical_form_payload["name"] if physical_form_payload else None
                ),
            }
            results.append(item_payload)

            if group_mode:
                PublicCatalogService._append_grouped_item(
                    grouped=grouped,
                    global_item=global_item,
                    ingredient_payload=ingredient_payload,
                    variation_payload=variation_payload,
                    physical_form_payload=physical_form_payload,
                    function_names=function_names,
                    application_names=application_names,
                    category_tag_names=category_tag_names,
                    display_name=display_name,
                )

        if group_mode:
            return {"success": True, "results": list((grouped or {}).values())}
        return {"success": True, "results": results}

    @staticmethod
    def build_public_global_item_search_payload(
        *,
        query_text: str,
        item_type: str | None,
        group: str | None,
        limit: int = 25,
    ) -> dict[str, Any]:
        return PublicCatalogService.search_global_items(
            query_text=query_text,
            item_type=item_type,
            group_mode=(
                group == "ingredient" and (not item_type or item_type == "ingredient")
            ),
            limit=limit,
        )

    @staticmethod
    def _display_name(
        *,
        fallback_name: str,
        ingredient_payload: dict[str, Any] | None,
        variation_payload: dict[str, Any] | None,
        physical_form_payload: dict[str, Any] | None,
    ) -> str:
        if (
            ingredient_payload
            and variation_payload
            and not variation_payload.get("form_bypass")
        ):
            return f"{ingredient_payload['name']}, {variation_payload['name']}"
        if ingredient_payload and physical_form_payload:
            return f"{ingredient_payload['name']} ({physical_form_payload['name']})"
        if ingredient_payload:
            return str(ingredient_payload["name"])
        return fallback_name

    @staticmethod
    def _append_grouped_item(
        *,
        grouped: OrderedDict[str, dict[str, Any]] | None,
        global_item: GlobalItem,
        ingredient_payload: dict[str, Any] | None,
        variation_payload: dict[str, Any] | None,
        physical_form_payload: dict[str, Any] | None,
        function_names: list[str],
        application_names: list[str],
        category_tag_names: list[str],
        display_name: str,
    ) -> None:
        if grouped is None:
            return

        group_key = (
            ingredient_payload["id"] if ingredient_payload else f"item-{global_item.id}"
        )
        group_entry = grouped.get(group_key)
        if not group_entry:
            group_entry = {
                "id": (
                    ingredient_payload["id"] if ingredient_payload else global_item.id
                ),
                "ingredient_id": (
                    ingredient_payload["id"] if ingredient_payload else None
                ),
                "name": (
                    ingredient_payload["name"] if ingredient_payload else display_name
                ),
                "text": (
                    ingredient_payload["name"] if ingredient_payload else display_name
                ),
                "display_name": (
                    ingredient_payload["name"] if ingredient_payload else display_name
                ),
                "item_type": global_item.item_type,
                "ingredient": ingredient_payload,
                "ingredient_category_id": (
                    ingredient_payload["ingredient_category_id"]
                    if ingredient_payload
                    else None
                ),
                "ingredient_category_name": (
                    ingredient_payload["ingredient_category_name"]
                    if ingredient_payload
                    else None
                ),
                "forms": [],
            }
            grouped[group_key] = group_entry

        group_entry["forms"].append(
            {
                "id": global_item.id,
                "name": display_name,
                "text": display_name,
                "display_name": display_name,
                "raw_name": global_item.name,
                "item_type": global_item.item_type,
                "ingredient_id": (
                    ingredient_payload["id"] if ingredient_payload else None
                ),
                "ingredient_name": (
                    ingredient_payload["name"] if ingredient_payload else None
                ),
                "variation": variation_payload,
                "variation_id": variation_payload["id"] if variation_payload else None,
                "variation_name": (
                    variation_payload["name"] if variation_payload else None
                ),
                "variation_slug": (
                    variation_payload["slug"] if variation_payload else None
                ),
                "physical_form": physical_form_payload,
                "physical_form_name": (
                    physical_form_payload["name"] if physical_form_payload else None
                ),
                "default_unit": global_item.default_unit,
                "unit": global_item.default_unit,
                "density": global_item.density,
                "default_is_perishable": global_item.default_is_perishable,
                "recommended_shelf_life_days": global_item.recommended_shelf_life_days,
                "recommended_fragrance_load_pct": (
                    global_item.recommended_fragrance_load_pct
                ),
                "aliases": global_item.aliases or [],
                "certifications": global_item.certifications or [],
                "functions": function_names,
                "applications": application_names,
                "inci_name": global_item.inci_name,
                "cas_number": getattr(global_item, "cas_number", None),
                "protein_content_pct": global_item.protein_content_pct,
                "brewing_color_srm": global_item.brewing_color_srm,
                "brewing_potential_sg": global_item.brewing_potential_sg,
                "brewing_diastatic_power_lintner": (
                    global_item.brewing_diastatic_power_lintner
                ),
                "saponification_value": getattr(
                    global_item, "saponification_value", None
                ),
                "iodine_value": getattr(global_item, "iodine_value", None),
                "fatty_acid_profile": getattr(global_item, "fatty_acid_profile", None),
                "melting_point_c": getattr(global_item, "melting_point_c", None),
                "flash_point_c": getattr(global_item, "flash_point_c", None),
                "moisture_content_percent": getattr(
                    global_item, "moisture_content_percent", None
                ),
                "comedogenic_rating": getattr(global_item, "comedogenic_rating", None),
                "ph_value": getattr(global_item, "ph_value", None),
                "category_tags": category_tag_names,
            }
        )
