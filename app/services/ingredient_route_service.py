"""Ingredient-route service boundary.

Synopsis:
Encapsulates ingredient API route data/session access so
`api/ingredient_routes.py` stays transport-focused.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import GlobalItem, IngredientCategory, InventoryItem
from app.models.ingredient_reference import IngredientDefinition, PhysicalForm, Variation

logger = logging.getLogger(__name__)


class IngredientRouteService:
    """Data/session helpers for ingredient API route workflows."""

    @staticmethod
    def list_global_active_categories() -> list[dict[str, Any]]:
        categories = (
            IngredientCategory.scoped()
            .filter_by(organization_id=None, is_active=True, is_global_category=True)
            .order_by(IngredientCategory.name.asc())
            .all()
        )
        return [
            {"id": cat.id, "name": cat.name, "default_density": cat.default_density}
            for cat in categories
        ]

    @staticmethod
    def list_global_ingredient_categories() -> list[dict[str, Any]]:
        return IngredientRouteService.list_global_active_categories()

    @staticmethod
    def get_inventory_item_or_404(*, inventory_item_id: int) -> InventoryItem:
        return InventoryItem.scoped().filter_by(id=inventory_item_id).first_or_404()

    @staticmethod
    def get_effective_ingredient_density(*, inventory_item_id: int) -> float:
        ingredient = IngredientRouteService.get_inventory_item_or_404(
            inventory_item_id=inventory_item_id
        )
        if ingredient.density:
            return ingredient.density
        if ingredient.category:
            return ingredient.category.default_density
        return 1.0

    @staticmethod
    def search_inventory_ingredients(
        *,
        query_text: str,
        organization_id: int | None,
        limit: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        query = InventoryItem.scoped().options(
            joinedload(InventoryItem.global_item).joinedload(GlobalItem.ingredient),
            joinedload(InventoryItem.global_item)
            .joinedload(GlobalItem.variation)
            .joinedload(Variation.physical_form),
        )
        if organization_id:
            query = query.filter(InventoryItem.organization_id == organization_id)

        rows = (
            query.filter(
                InventoryItem.type == "ingredient",
                InventoryItem.name.ilike(f"%{query_text}%"),
            )
            .order_by(func.length(InventoryItem.name).asc())
            .limit(limit)
            .all()
        )

        payload: list[dict[str, Any]] = []
        for item in rows:
            global_obj = getattr(item, "global_item", None)
            ingredient_obj = getattr(global_obj, "ingredient", None) if global_obj else None
            variation_obj = getattr(global_obj, "variation", None) if global_obj else None
            physical_form_obj = (
                getattr(variation_obj, "physical_form", None) if variation_obj else None
            )
            payload.append(
                {
                    "id": item.id,
                    "text": item.name,
                    "category": item.category.name if item.category else None,
                    "unit": item.unit,
                    "density": item.density,
                    "type": item.type,
                    "global_item_id": item.global_item_id,
                    "ingredient_id": ingredient_obj.id if ingredient_obj else None,
                    "ingredient_name": ingredient_obj.name if ingredient_obj else item.name,
                    "variation_id": variation_obj.id if variation_obj else None,
                    "variation_name": variation_obj.name if variation_obj else None,
                    "physical_form_id": physical_form_obj.id if physical_form_obj else None,
                    "physical_form_name": (
                        physical_form_obj.name if physical_form_obj else None
                    ),
                    "cost_per_unit": item.cost_per_unit,
                    "inci_name": getattr(item, "inci_name", None),
                    "cas_number": getattr(item, "cas_number", None),
                }
            )
        return {"results": payload}

    @staticmethod
    def search_ingredient_definitions(
        *,
        query_text: str,
        limit: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        rows = (
            IngredientDefinition.query.filter(
                or_(
                    IngredientDefinition.name.ilike(f"%{query_text}%"),
                    IngredientDefinition.inci_name.ilike(f"%{query_text}%"),
                    IngredientDefinition.cas_number.ilike(f"%{query_text}%"),
                ),
                IngredientDefinition.is_active,
            )
            .order_by(func.length(IngredientDefinition.name).asc())
            .limit(limit)
            .all()
        )
        return {
            "results": [
                {
                    "id": definition.id,
                    "name": definition.name,
                    "slug": definition.slug,
                    "inci_name": definition.inci_name,
                    "cas_number": definition.cas_number,
                    "ingredient_category_id": definition.ingredient_category_id,
                    "ingredient_category_name": (
                        definition.category.name if definition.category else None
                    ),
                    "description": definition.description,
                }
                for definition in rows
            ]
        }

    @staticmethod
    def list_forms_for_ingredient_definition(
        *, ingredient_id: int
    ) -> dict[str, dict[str, Any] | list[dict[str, Any]]]:
        ingredient = db.get_or_404(IngredientDefinition, ingredient_id)
        items = (
            GlobalItem.query.filter(
                GlobalItem.ingredient_id == ingredient.id,
                not GlobalItem.is_archived,
            )
            .order_by(GlobalItem.name.asc())
            .all()
        )

        payload: list[dict[str, Any]] = []
        for item in items:
            variation_obj = getattr(item, "variation", None)
            physical_form_obj = (
                getattr(variation_obj, "physical_form", None) if variation_obj else None
            )
            payload.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "variation_id": variation_obj.id if variation_obj else None,
                    "variation_name": variation_obj.name if variation_obj else None,
                    "variation_slug": variation_obj.slug if variation_obj else None,
                    "variation": (
                        {
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
                        if variation_obj
                        else None
                    ),
                    "physical_form_name": (
                        physical_form_obj.name if physical_form_obj else None
                    ),
                    "physical_form_id": physical_form_obj.id if physical_form_obj else None,
                    "inci_name": getattr(item, "inci_name", None),
                    "cas_number": getattr(item, "cas_number", None),
                }
            )

        return {
            "ingredient": {
                "id": ingredient.id,
                "name": ingredient.name,
                "inci_name": ingredient.inci_name,
                "cas_number": ingredient.cas_number,
                "ingredient_category_id": ingredient.ingredient_category_id,
                "ingredient_category_name": (
                    ingredient.category.name if ingredient.category else None
                ),
            },
            "items": payload,
        }

    @staticmethod
    def search_physical_forms(
        *,
        query_text: str,
        limit: int = 30,
    ) -> dict[str, list[dict[str, Any]]]:
        query = PhysicalForm.query.filter(PhysicalForm.is_active)
        if query_text:
            ilike_term = f"%{query_text}%"
            query = query.filter(
                or_(PhysicalForm.name.ilike(ilike_term), PhysicalForm.slug.ilike(ilike_term))
            )
        forms = (
            query.order_by(func.length(PhysicalForm.name).asc(), PhysicalForm.name.asc())
            .limit(limit)
            .all()
        )
        return {
            "results": [
                {
                    "id": physical_form.id,
                    "name": physical_form.name,
                    "slug": physical_form.slug,
                    "description": physical_form.description,
                }
                for physical_form in forms
            ]
        }

    @staticmethod
    def search_variations(
        *,
        query_text: str,
        limit: int = 30,
    ) -> dict[str, list[dict[str, Any]]]:
        query = Variation.query.filter(Variation.is_active)
        if query_text:
            ilike_term = f"%{query_text}%"
            query = query.filter(
                or_(Variation.name.ilike(ilike_term), Variation.slug.ilike(ilike_term))
            )
        rows = (
            query.order_by(func.length(Variation.name).asc(), Variation.name.asc())
            .limit(limit)
            .all()
        )
        return {
            "results": [
                {
                    "id": variation.id,
                    "name": variation.name,
                    "slug": variation.slug,
                    "description": variation.description,
                    "physical_form_name": (
                        variation.physical_form.name if variation.physical_form else None
                    ),
                    "physical_form_id": variation.physical_form_id,
                    "default_unit": variation.default_unit,
                    "form_bypass": variation.form_bypass,
                }
                for variation in rows
            ]
        }

    @staticmethod
    def create_or_link_inventory_item(
        *,
        data: dict[str, Any],
        organization_id: int | None,
        actor_user_id: int | None,
    ) -> tuple[dict[str, Any], int]:
        name = (data.get("name") or "").strip()
        inv_type = (data.get("type") or "ingredient").strip()
        unit = (data.get("unit") or "").strip()
        global_item_id = data.get("global_item_id")
        if not name:
            return {"success": False, "error": "Name required"}, 400

        existing = (
            InventoryItem.scoped()
            .filter_by(organization_id=organization_id, name=name, type=inv_type)
            .order_by(InventoryItem.id.asc())
            .first()
        )
        if existing:
            return (
                {
                    "success": True,
                    "item": {
                        "id": existing.id,
                        "name": existing.name,
                        "unit": existing.unit,
                        "type": existing.type,
                        "global_item_id": getattr(existing, "global_item_id", None),
                    },
                },
                200,
            )

        global_item = None
        if global_item_id:
            global_item = db.session.get(GlobalItem, int(global_item_id))
        else:
            global_item = (
                GlobalItem.query.filter(
                    func.lower(GlobalItem.name) == func.lower(db.literal(name)),
                    GlobalItem.item_type == inv_type,
                    not GlobalItem.is_archived,
                )
                .order_by(GlobalItem.id.asc())
                .first()
            )

        new_item = InventoryItem(
            name=name,
            unit=(
                unit
                or (
                    global_item.default_unit
                    if global_item and global_item.default_unit
                    else "count" if inv_type == "container" else "g"
                )
            ),
            type=inv_type,
            quantity=0.0,
            organization_id=organization_id,
            created_by=actor_user_id,
        )
        if global_item:
            new_item.global_item_id = global_item.id
            new_item.ownership = "global"
            if inv_type == "container" and getattr(global_item, "capacity", None):
                new_item.capacity = global_item.capacity
                new_item.capacity_unit = global_item.capacity_unit

        db.session.add(new_item)
        db.session.commit()
        return (
            {
                "success": True,
                "item": {
                    "id": new_item.id,
                    "name": new_item.name,
                    "unit": new_item.unit,
                    "type": new_item.type,
                    "global_item_id": getattr(new_item, "global_item_id", None),
                },
            },
            200,
        )

    @staticmethod
    def search_global_items_payload(
        *,
        query_text: str,
        item_type: str,
        group_by_ingredient: bool,
        limit: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        query = GlobalItem.query.filter(not GlobalItem.is_archived)
        if item_type:
            query = query.filter(GlobalItem.item_type == item_type)

        ilike_term = f"%{query_text}%"
        name_match = GlobalItem.name.ilike(ilike_term)
        try:
            alias_match = GlobalItem.aliases.cast(db.String).ilike(ilike_term)
            items = (
                query.filter(or_(name_match, alias_match))
                .order_by(func.length(GlobalItem.name).asc())
                .limit(limit)
                .all()
            )
        except Exception:
            logger.warning(
                "Suppressed exception fallback at app/services/ingredient_route_service.py:324",
                exc_info=True,
            )
            items = (
                query.filter(name_match)
                .order_by(func.length(GlobalItem.name).asc())
                .limit(limit)
                .all()
            )

        group_mode = group_by_ingredient and (not item_type or item_type == "ingredient")
        grouped = OrderedDict() if group_mode else None
        results: list[dict[str, Any]] = []
        for gi in items:
            ingredient_obj = gi.ingredient if getattr(gi, "ingredient", None) else None
            ingredient_category_obj = (
                ingredient_obj.category
                if ingredient_obj and getattr(ingredient_obj, "category", None)
                else None
            )
            variation_obj = gi.variation if getattr(gi, "variation", None) else None
            physical_form_obj = (
                variation_obj.physical_form
                if variation_obj and getattr(variation_obj, "physical_form", None)
                else (gi.physical_form if getattr(gi, "physical_form", None) else None)
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
                        ingredient_category_obj.name if ingredient_category_obj else None
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
            function_names = [tag.name for tag in getattr(gi, "functions", [])]
            application_names = [tag.name for tag in getattr(gi, "applications", [])]
            ingredient_category_name = (
                gi.ingredient_category.name if gi.ingredient_category else None
            )

            display_name = gi.name
            if (
                ingredient_payload
                and variation_payload
                and not variation_payload.get("form_bypass")
            ):
                display_name = (
                    f"{ingredient_payload['name']}, {variation_payload['name']}"
                )
            elif ingredient_payload and physical_form_payload:
                display_name = (
                    f"{ingredient_payload['name']} ({physical_form_payload['name']})"
                )
            elif ingredient_payload:
                display_name = ingredient_payload["name"]

            item_payload = {
                "id": gi.id,
                "name": display_name,
                "text": display_name,
                "display_name": display_name,
                "raw_name": gi.name,
                "item_type": gi.item_type,
                "ingredient": ingredient_payload,
                "variation": variation_payload,
                "variation_id": variation_payload["id"] if variation_payload else None,
                "variation_name": variation_payload["name"] if variation_payload else None,
                "variation_slug": variation_payload["slug"] if variation_payload else None,
                "physical_form": physical_form_payload,
                "functions": function_names,
                "applications": application_names,
                "default_unit": gi.default_unit,
                "density": gi.density,
                "capacity": gi.capacity,
                "capacity_unit": gi.capacity_unit,
                "container_material": getattr(gi, "container_material", None),
                "container_type": getattr(gi, "container_type", None),
                "container_style": getattr(gi, "container_style", None),
                "container_color": getattr(gi, "container_color", None),
                "aliases": gi.aliases,
                "default_is_perishable": gi.default_is_perishable,
                "recommended_shelf_life_days": gi.recommended_shelf_life_days,
                "recommended_fragrance_load_pct": gi.recommended_fragrance_load_pct,
                "inci_name": gi.inci_name,
                "cas_number": getattr(gi, "cas_number", None),
                "protein_content_pct": gi.protein_content_pct,
                "brewing_color_srm": gi.brewing_color_srm,
                "brewing_potential_sg": gi.brewing_potential_sg,
                "brewing_diastatic_power_lintner": gi.brewing_diastatic_power_lintner,
                "certifications": gi.certifications or [],
                "ingredient_category_id": gi.ingredient_category_id,
                "ingredient_category_name": ingredient_category_name,
                "ingredient_name": (
                    ingredient_payload["name"] if ingredient_payload else None
                ),
                "physical_form_name": (
                    physical_form_payload["name"] if physical_form_payload else None
                ),
                "saponification_value": getattr(gi, "saponification_value", None),
                "iodine_value": getattr(gi, "iodine_value", None),
                "fatty_acid_profile": getattr(gi, "fatty_acid_profile", None),
                "melting_point_c": getattr(gi, "melting_point_c", None),
                "flash_point_c": getattr(gi, "flash_point_c", None),
                "moisture_content_percent": getattr(gi, "moisture_content_percent", None),
                "comedogenic_rating": getattr(gi, "comedogenic_rating", None),
                "ph_value": getattr(gi, "ph_value", None),
            }
            results.append(item_payload)

            if group_mode:
                group_key = ingredient_payload["id"] if ingredient_payload else f"item-{gi.id}"
                group_entry = grouped.get(group_key)
                if not group_entry:
                    group_entry = {
                        "id": ingredient_payload["id"] if ingredient_payload else gi.id,
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
                        "item_type": gi.item_type,
                        "ingredient": ingredient_payload,
                        "ingredient_category_id": (
                            ingredient_payload["ingredient_category_id"]
                            if ingredient_payload
                            else gi.ingredient_category_id
                        ),
                        "ingredient_category_name": (
                            ingredient_payload["ingredient_category_name"]
                            if ingredient_payload
                            else ingredient_category_name
                        ),
                        "forms": [],
                    }
                    grouped[group_key] = group_entry

                group_entry["forms"].append(
                    {
                        "id": gi.id,
                        "name": display_name,
                        "text": display_name,
                        "display_name": display_name,
                        "raw_name": gi.name,
                        "item_type": gi.item_type,
                        "ingredient_id": (
                            ingredient_payload["id"] if ingredient_payload else None
                        ),
                        "ingredient_name": (
                            ingredient_payload["name"] if ingredient_payload else None
                        ),
                        "variation": variation_payload,
                        "variation_id": (
                            variation_payload["id"] if variation_payload else None
                        ),
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
                        "default_unit": gi.default_unit,
                        "density": gi.density,
                        "default_is_perishable": gi.default_is_perishable,
                        "recommended_shelf_life_days": gi.recommended_shelf_life_days,
                        "recommended_fragrance_load_pct": gi.recommended_fragrance_load_pct,
                        "aliases": gi.aliases or [],
                        "certifications": gi.certifications or [],
                        "functions": function_names,
                        "applications": application_names,
                        "inci_name": gi.inci_name,
                        "cas_number": getattr(gi, "cas_number", None),
                        "protein_content_pct": gi.protein_content_pct,
                        "brewing_color_srm": gi.brewing_color_srm,
                        "brewing_potential_sg": gi.brewing_potential_sg,
                        "brewing_diastatic_power_lintner": gi.brewing_diastatic_power_lintner,
                        "ingredient_category_id": gi.ingredient_category_id,
                        "ingredient_category_name": ingredient_category_name,
                        "saponification_value": getattr(gi, "saponification_value", None),
                        "iodine_value": getattr(gi, "iodine_value", None),
                        "fatty_acid_profile": getattr(gi, "fatty_acid_profile", None),
                        "melting_point_c": getattr(gi, "melting_point_c", None),
                        "flash_point_c": getattr(gi, "flash_point_c", None),
                        "moisture_content_percent": getattr(
                            gi, "moisture_content_percent", None
                        ),
                        "comedogenic_rating": getattr(gi, "comedogenic_rating", None),
                        "ph_value": getattr(gi, "ph_value", None),
                    }
                )

        if group_mode:
            return {"results": list(grouped.values())}
        return {"results": results}

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
