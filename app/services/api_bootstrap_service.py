"""API bootstrap/query service boundary.

Synopsis:
Centralizes read/query helpers used by API bootstrap and lookup routes so the
blueprint layer stays transport-focused.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from typing import Any

from app.extensions import db
from app.models import InventoryItem
from app.models.product_category import ProductCategory


class ApiBootstrapService:
    """Service helpers for API route query/persistence boundaries."""

    @staticmethod
    def get_inventory_item_or_404(
        *,
        item_id: int,
        organization_id: int | None,
    ) -> InventoryItem:
        return (
            InventoryItem.scoped()
            .filter_by(id=item_id, organization_id=organization_id)
            .first_or_404()
        )

    @staticmethod
    def get_category_or_404(cat_id: int) -> ProductCategory:
        return db.get_or_404(ProductCategory, cat_id)

    @staticmethod
    def list_ingredients_for_org(organization_id: int | None) -> list[dict[str, Any]]:
        query = InventoryItem.scoped().filter_by(type="ingredient")
        if organization_id:
            query = query.filter_by(organization_id=organization_id)

        ingredients = query.order_by(InventoryItem.name).all()
        return [
            {
                "id": ing.id,
                "name": ing.name,
                "density": ing.density,
                "type": ing.type,
                "unit": ing.unit,
            }
            for ing in ingredients
        ]

    @staticmethod
    def get_inventory_item_density(
        *,
        ingredient_id: int | None,
    ) -> float | None:
        if not ingredient_id:
            return None
        ingredient = db.session.get(InventoryItem, ingredient_id)
        return ingredient.density if ingredient else None
