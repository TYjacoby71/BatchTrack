"""Developer product-category management service.

Synopsis:
Encapsulates create/read/update/delete rules for product categories so
developer routes remain transport-focused and do not touch persistence directly.

Glossary:
- Conflict: Case-insensitive duplicate category name.
- In use: Category referenced by at least one product or recipe.
"""

from __future__ import annotations

from app.extensions import db
from app.models import Product, ProductCategory, Recipe


class ProductCategoryService:
    """Service layer for developer product category CRUD."""

    @staticmethod
    def list_categories() -> list[ProductCategory]:
        return ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    @staticmethod
    def get_category_or_404(cat_id: int) -> ProductCategory:
        return db.get_or_404(ProductCategory, cat_id)

    @staticmethod
    def normalize_form_inputs(
        *,
        name: str | None,
        is_typically_portioned_raw: str | None,
        sku_name_template: str | None,
    ) -> tuple[str, bool, str | None]:
        normalized_name = (name or "").strip()
        is_typically_portioned = is_typically_portioned_raw == "on"
        normalized_template = (sku_name_template or "").strip() or None
        return normalized_name, is_typically_portioned, normalized_template

    @staticmethod
    def validate_name_required(name: str) -> tuple[bool, str | None]:
        if not name:
            return False, "Name is required"
        return True, None

    @staticmethod
    def find_conflict(
        *,
        name: str,
        exclude_category_id: int | None = None,
    ) -> ProductCategory | None:
        query = ProductCategory.query.filter(ProductCategory.name.ilike(name))
        if exclude_category_id is not None:
            query = query.filter(ProductCategory.id != exclude_category_id)
        return query.first()

    @staticmethod
    def create_category(
        *,
        name: str,
        is_typically_portioned: bool,
        sku_name_template: str | None,
    ) -> ProductCategory:
        category = ProductCategory(
            name=name,
            is_typically_portioned=is_typically_portioned,
            sku_name_template=sku_name_template,
        )
        db.session.add(category)
        db.session.commit()
        return category

    @staticmethod
    def update_category(
        category: ProductCategory,
        *,
        name: str,
        is_typically_portioned: bool,
        sku_name_template: str | None,
    ) -> ProductCategory:
        category.name = name
        category.is_typically_portioned = is_typically_portioned
        category.sku_name_template = sku_name_template
        db.session.commit()
        return category

    @staticmethod
    def is_category_in_use(category: ProductCategory) -> bool:
        return bool(
            db.session.query(Product).filter_by(category_id=category.id).first()
            or db.session.query(Recipe).filter_by(category_id=category.id).first()
        )

    @staticmethod
    def delete_category(category: ProductCategory) -> None:
        db.session.delete(category)
        db.session.commit()
