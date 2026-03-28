"""Recipe AJAX service boundary.

Synopsis:
Encapsulates quick-add ingredient lookup/create persistence so AJAX recipe routes
remain transport-focused.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import InventoryItem


class RecipeAjaxService:
    """Service helpers for recipe AJAX endpoints."""

    @staticmethod
    def find_existing_inventory_item(
        *,
        name: str,
        organization_id: int | None,
    ) -> InventoryItem | None:
        return (
            InventoryItem.scoped()
            .filter_by(name=name, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def create_inventory_item(
        *,
        name: str,
        unit: str,
        ingredient_type: str,
        organization_id: int | None,
        created_by: int | None,
    ) -> InventoryItem:
        ingredient = InventoryItem(
            name=name,
            unit=unit,
            type=ingredient_type,
            quantity=0.0,
            organization_id=organization_id,
            created_by=created_by,
        )
        db.session.add(ingredient)
        db.session.commit()
        return ingredient
