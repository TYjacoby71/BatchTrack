"""Developer reference-routes service boundary.

Synopsis:
Owns reference-route persistence/query operations so
`app/blueprints/developer/views/reference_routes.py` remains transport-focused.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func

from app.extensions import db
from app.models import GlobalItem
from app.models.category import IngredientCategory
from app.models.ingredient_reference import (
    ApplicationTag,
    FunctionTag,
    IngredientCategoryTag,
    PhysicalForm,
    Variation,
)
from app.utils.seo import slugify_value


class ReferenceRouteService:
    """Data/session helpers for developer reference routes."""

    logger = logging.getLogger(__name__)

    @staticmethod
    def _generate_unique_slug(model, seed: str) -> str:
        base_slug = slugify_value(seed or "item")
        candidate = base_slug
        counter = 2
        while model.query.filter_by(slug=candidate).first():
            candidate = f"{base_slug}-{counter}"
            counter += 1
        return candidate

    @staticmethod
    def get_reference_categories_context() -> dict[str, Any]:
        existing_categories = (
            IngredientCategory.query.filter_by(
                organization_id=None,
                is_active=True,
                is_global_category=True,
            )
            .order_by(IngredientCategory.name)
            .all()
        )

        categories = [cat.name for cat in existing_categories]
        global_items_by_category: dict[str, list[Any]] = {}
        category_densities: dict[str, float] = {}

        for category_obj in existing_categories:
            items = GlobalItem.query.filter_by(
                ingredient_category_id=category_obj.id, is_archived=False
            ).all()
            global_items_by_category[category_obj.name] = items
            if category_obj.default_density:
                category_densities[category_obj.name] = category_obj.default_density

        return {
            "categories": categories,
            "global_items_by_category": global_items_by_category,
            "category_densities": category_densities,
        }

    @staticmethod
    def add_reference_category(data: dict[str, Any]) -> dict[str, Any]:
        try:
            category_name = (data.get("name") or "").strip()
            default_density = data.get("default_density")

            if not category_name:
                return {"success": False, "error": "Category name is required"}

            existing = IngredientCategory.query.filter_by(
                name=category_name,
                organization_id=None,
            ).first()
            if existing:
                return {"success": False, "error": "Category already exists"}

            new_category = IngredientCategory(
                name=category_name,
                is_global_category=True,
                organization_id=None,
                is_active=True,
                default_density=(
                    default_density
                    if isinstance(default_density, (int, float))
                    else None
                ),
            )
            db.session.add(new_category)
            db.session.commit()
            return {
                "success": True,
                "message": f'Category "{category_name}" added successfully',
            }
        except Exception as exc:
            ReferenceRouteService.logger.warning(
                "Suppressed exception fallback at app/services/developer/reference_route_service.py:add_reference_category",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def delete_reference_category(data: dict[str, Any]) -> dict[str, Any]:
        try:
            category_name = (data.get("name") or "").strip()
            if not category_name:
                return {"success": False, "error": "Category name is required"}

            category = IngredientCategory.query.filter_by(
                name=category_name,
                organization_id=None,
            ).first()
            if not category:
                return {"success": False, "error": "Category not found"}

            linked_items = GlobalItem.query.filter_by(
                ingredient_category_id=category.id
            ).count()
            if linked_items:
                return {
                    "success": False,
                    "error": f"Category is linked to {linked_items} global items. Reassign before deleting.",
                }

            db.session.delete(category)
            db.session.commit()
            return {
                "success": True,
                "message": f'Category "{category_name}" deleted successfully',
            }
        except Exception as exc:
            ReferenceRouteService.logger.warning(
                "Suppressed exception fallback at app/services/developer/reference_route_service.py:delete_reference_category",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def update_reference_category_density(data: dict[str, Any]) -> dict[str, Any]:
        try:
            category_name = (data.get("name") or "").strip()
            density = data.get("default_density")

            if not category_name:
                return {"success": False, "error": "Category name is required"}
            if density in (None, ""):
                return {"success": False, "error": "Density value is required"}

            try:
                density_value = float(density)
            except ValueError:
                return {"success": False, "error": "Density must be a numeric value"}

            category = IngredientCategory.query.filter_by(
                name=category_name,
                organization_id=None,
            ).first()
            if not category:
                return {"success": False, "error": "Category not found"}

            category.default_density = density_value
            GlobalItem.query.filter_by(ingredient_category_id=category.id).update(
                {GlobalItem.density: density_value}
            )
            db.session.commit()
            return {
                "success": True,
                "message": f'Category "{category_name}" density set to {density_value}',
            }
        except Exception as exc:
            ReferenceRouteService.logger.warning(
                "Suppressed exception fallback at app/services/developer/reference_route_service.py:update_reference_category_density",
                exc_info=True,
            )
            db.session.rollback()
            return {"success": False, "error": str(exc)}

    @staticmethod
    def calculate_category_density(data: dict[str, Any]) -> dict[str, Any]:
        category_name = (data.get("name") or "").strip()
        if not category_name:
            return {"success": False, "error": "Category name is required"}

        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None,
        ).first()
        if not category:
            return {"success": False, "error": "Category not found"}

        densities = [
            item.density
            for item in GlobalItem.query.filter_by(ingredient_category_id=category.id)
            .filter(GlobalItem.density.isnot(None))
            .all()
            if item.density
        ]
        if not densities:
            return {
                "success": False,
                "error": "No items with valid density values found",
            }

        calculated_density = sum(densities) / len(densities)
        return {
            "success": True,
            "calculated_density": calculated_density,
            "items_count": len(densities),
            "message": (
                f"Calculated density: {calculated_density:.3f} g/ml from {len(densities)} items"
            ),
        }

    @staticmethod
    def get_ingredient_attributes_context() -> dict[str, Any]:
        forms = PhysicalForm.query.order_by(PhysicalForm.name.asc()).all()
        variations = Variation.query.order_by(Variation.name.asc()).all()
        variation_usage_rows = (
            db.session.query(Variation.id, func.count(GlobalItem.id))
            .join(GlobalItem, GlobalItem.variation_id == Variation.id)
            .filter(not GlobalItem.is_archived)
            .group_by(Variation.id)
            .all()
        )
        variation_usage = {
            variation_id: count for variation_id, count in variation_usage_rows
        }

        return {
            "physical_forms": forms,
            "variations": variations,
            "variation_usage": variation_usage,
            "function_tags": FunctionTag.query.order_by(FunctionTag.name.asc()).all(),
            "application_tags": ApplicationTag.query.order_by(
                ApplicationTag.name.asc()
            ).all(),
            "category_tags": IngredientCategoryTag.query.order_by(
                IngredientCategoryTag.name.asc()
            ).all(),
        }

    @staticmethod
    def create_physical_form(name: str, description: str | None) -> tuple[bool, str]:
        existing = (
            PhysicalForm.query.filter(func.lower(PhysicalForm.name) == func.lower(name))
            .order_by(PhysicalForm.id.asc())
            .first()
        )
        if existing:
            return False, f'Physical form "{name}" already exists.'

        new_form = PhysicalForm(
            name=name,
            slug=ReferenceRouteService._generate_unique_slug(PhysicalForm, name),
            description=description,
            is_active=True,
        )
        db.session.add(new_form)
        db.session.commit()
        return True, f'Physical form "{name}" created.'

    @staticmethod
    def toggle_physical_form(form_id: int) -> PhysicalForm:
        physical_form = db.get_or_404(PhysicalForm, form_id)
        physical_form.is_active = not physical_form.is_active
        db.session.commit()
        return physical_form

    @staticmethod
    def create_variation(
        *,
        name: str,
        physical_form_id: str,
        description: str | None,
        default_unit: str | None,
        form_bypass: bool,
    ) -> tuple[bool, str]:
        existing = (
            Variation.query.filter(func.lower(Variation.name) == func.lower(name))
            .order_by(Variation.id.asc())
            .first()
        )
        if existing:
            return False, f'Variation "{name}" already exists.'

        physical_form = None
        if physical_form_id:
            try:
                physical_form = db.session.get(PhysicalForm, int(physical_form_id))
            except (TypeError, ValueError):
                physical_form = None

        variation = Variation(
            name=name,
            slug=ReferenceRouteService._generate_unique_slug(Variation, name),
            physical_form=physical_form,
            description=description,
            default_unit=default_unit,
            form_bypass=form_bypass,
            is_active=True,
        )
        db.session.add(variation)
        db.session.commit()
        return True, f'Variation "{name}" created.'

    @staticmethod
    def toggle_variation(variation_id: int) -> Variation:
        variation = db.get_or_404(Variation, variation_id)
        variation.is_active = not variation.is_active
        db.session.commit()
        return variation

    @staticmethod
    def _save_tag_entry(model, name: str, description: str | None) -> None:
        existing = model.query.filter(
            func.lower(model.name) == func.lower(name)
        ).first()
        if existing:
            return
        tag = model(
            name=name,
            slug=ReferenceRouteService._generate_unique_slug(model, name),
            description=description or None,
            is_active=True,
        )
        db.session.add(tag)

    @staticmethod
    def save_function_tag(name: str, description: str | None) -> None:
        ReferenceRouteService._save_tag_entry(FunctionTag, name, description)
        db.session.commit()

    @staticmethod
    def save_application_tag(name: str, description: str | None) -> None:
        ReferenceRouteService._save_tag_entry(ApplicationTag, name, description)
        db.session.commit()

    @staticmethod
    def save_category_tag(name: str, description: str | None) -> None:
        ReferenceRouteService._save_tag_entry(IngredientCategoryTag, name, description)
        db.session.commit()
