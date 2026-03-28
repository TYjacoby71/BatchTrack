"""Developer global-item route service boundary.

Synopsis:
Owns global-item route persistence/query operations so
`app/blueprints/developer/views/global_item_routes.py` can stay transport-focused.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from sqlalchemy import or_

from app.extensions import db
from app.models import GlobalItem
from app.models.category import IngredientCategory
from app.models.ingredient_reference import (
    ApplicationTag,
    FunctionTag,
    IngredientCategoryTag,
    IngredientDefinition,
    PhysicalForm,
    Variation,
)
from app.utils.seo import slugify_value


class GlobalItemRouteService:
    """Data/session helpers for developer global-item routes."""

    @staticmethod
    def get_global_item_or_404(*, item_id: int):
        return db.get_or_404(GlobalItem, item_id)

    @staticmethod
    def list_global_ingredient_categories():
        return (
            IngredientCategory.query.filter_by(
                organization_id=None,
                is_active=True,
                is_global_category=True,
            )
            .order_by(IngredientCategory.name)
            .all()
        )

    @staticmethod
    def list_physical_forms():
        return PhysicalForm.query.order_by(PhysicalForm.name).all()

    @staticmethod
    def list_existing_items_for_ingredient(*, ingredient_id: int):
        return (
            GlobalItem.query.filter(
                GlobalItem.ingredient_id == ingredient_id,
                not GlobalItem.is_archived,
            )
            .order_by(GlobalItem.name.asc())
            .all()
        )

    @staticmethod
    def get_ingredient_definition(*, ingredient_id: int):
        return db.session.get(IngredientDefinition, ingredient_id)

    @staticmethod
    def get_variation(*, variation_id: int):
        return db.session.get(Variation, variation_id)

    @staticmethod
    def get_physical_form(*, physical_form_id: int):
        return db.session.get(PhysicalForm, physical_form_id)

    @staticmethod
    def get_global_category(*, category_id: int):
        return IngredientCategory.query.filter_by(
            id=category_id,
            organization_id=None,
            is_global_category=True,
        ).first()

    @staticmethod
    def find_existing_global_item_by_name_and_type(*, name: str, item_type: str):
        return GlobalItem.query.filter_by(name=name, item_type=item_type).first()

    @staticmethod
    def find_tag_by_slug_or_name(*, model, slug_candidate: str, name: str):
        return model.query.filter(
            or_(model.slug == slug_candidate, model.name.ilike(name))
        ).first()

    @staticmethod
    def slug_exists(*, model, slug: str) -> bool:
        return model.query.filter_by(slug=slug).first() is not None

    @staticmethod
    def create_tag(*, model, name: str, slug: str):
        tag = model(name=name, slug=slug)
        db.session.add(tag)
        return tag

    @staticmethod
    def generate_unique_slug(*, model, seed: str) -> str:
        base_slug = slugify_value(seed or "item")
        candidate = base_slug
        counter = 2
        while GlobalItemRouteService.slug_exists(model=model, slug=candidate):
            candidate = f"{base_slug}-{counter}"
            counter += 1
        return candidate

    @staticmethod
    def create_new_global_item(**kwargs):
        item = GlobalItem(**kwargs)
        db.session.add(item)
        return item

    @staticmethod
    def get_inventory_item(*, inventory_item_id: int):
        from app.models.inventory import InventoryItem

        return db.session.get(InventoryItem, inventory_item_id)

    @staticmethod
    def list_inventory_items_connected_to_global_item(*, global_item_id: int):
        from app.models.inventory import InventoryItem

        return InventoryItem.query.filter_by(global_item_id=global_item_id).all()

    @staticmethod
    def detach_inventory_items_from_global_item(*, inventory_items: list) -> None:
        for inv_item in inventory_items:
            inv_item.global_item_id = None
            inv_item.is_org_custom_item = True

    @staticmethod
    def delete_global_item(*, item) -> None:
        db.session.delete(item)

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()

    # Compatibility model handles for legacy helper signatures.
    FunctionTag = FunctionTag
    ApplicationTag = ApplicationTag
    IngredientCategoryTag = IngredientCategoryTag
