"""Product-variant route service boundary.

Synopsis:
Encapsulates product-variant route data/session access so
`products/product_variants.py` stays transport-focused.
"""

from __future__ import annotations

from app.extensions import db
from app.models import InventoryItem, ProductSKU
from app.models.product import Product, ProductVariant
from app.services.product_service import ProductService


class ProductVariantRouteService:
    """Data/session helpers for product-variant route workflows."""

    @staticmethod
    def get_product_for_org(
        *, product_id: int, organization_id: int | None
    ) -> Product | None:
        return (
            Product.scoped()
            .filter_by(id=product_id, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def get_product_for_variant_flow(
        *, product_id: int, organization_id: int | None
    ) -> Product | None:
        product = ProductVariantRouteService.get_product_for_org(
            product_id=product_id,
            organization_id=organization_id,
        )
        if product is not None:
            return product
        return ProductVariantRouteService.get_product_from_sku_id_for_org(
            sku_id=product_id,
            organization_id=organization_id,
        )

    @staticmethod
    def get_product_from_sku_id_for_org(
        *, sku_id: int, organization_id: int | None
    ) -> Product | None:
        base_sku = (
            ProductSKU.scoped()
            .filter_by(id=sku_id, organization_id=organization_id)
            .first()
        )
        if not base_sku or not base_sku.product_id:
            return None
        return db.session.get(Product, base_sku.product_id)

    @staticmethod
    def get_variant_for_product_by_name(
        *, product_id: int, variant_name: str
    ) -> ProductVariant | None:
        return (
            ProductVariant.scoped()
            .filter_by(product_id=product_id, name=variant_name)
            .first()
        )

    @staticmethod
    def list_active_skus_for_variant(
        *,
        product_id: int,
        variant_id: int,
        organization_id: int | None,
    ) -> list[ProductSKU]:
        return (
            ProductSKU.scoped()
            .filter_by(
                product_id=product_id,
                variant_id=variant_id,
                is_active=True,
                organization_id=organization_id,
            )
            .all()
        )

    @staticmethod
    def list_active_variant_skus_for_org(
        *,
        product_id: int,
        variant_id: int,
        organization_id: int | None,
    ) -> list[ProductSKU]:
        return ProductVariantRouteService.list_active_skus_for_variant(
            product_id=product_id,
            variant_id=variant_id,
            organization_id=organization_id,
        )

    @staticmethod
    def list_all_skus_for_variant(
        *,
        product_id: int,
        variant_id: int,
        organization_id: int | None,
    ) -> list[ProductSKU]:
        return (
            ProductSKU.scoped()
            .filter_by(
                product_id=product_id,
                variant_id=variant_id,
                organization_id=organization_id,
            )
            .all()
        )

    @staticmethod
    def list_variant_skus_for_org(
        *,
        product_id: int,
        variant_id: int,
        organization_id: int | None,
    ) -> list[ProductSKU]:
        return ProductVariantRouteService.list_all_skus_for_variant(
            product_id=product_id,
            variant_id=variant_id,
            organization_id=organization_id,
        )

    @staticmethod
    def list_available_containers() -> list[InventoryItem]:
        return (
            InventoryItem.scoped()
            .filter_by(type="container", is_archived=False)
            .filter(InventoryItem.quantity > 0)
            .all()
        )

    @staticmethod
    def list_available_containers_for_org(
        *, organization_id: int | None
    ) -> list[InventoryItem]:
        _ = organization_id
        return ProductVariantRouteService.list_available_containers()

    @staticmethod
    def get_base_bulk_sku_for_product(
        *,
        product_id: int,
        fallback_variant_id: int,
        base_variant_id: int | None,
        organization_id: int | None,
    ) -> ProductSKU | None:
        return (
            ProductSKU.scoped()
            .filter_by(
                product_id=product_id,
                variant_id=base_variant_id or fallback_variant_id,
                organization_id=organization_id,
            )
            .filter(ProductSKU.size_label.ilike("Bulk%"))
            .first()
        )

    @staticmethod
    def get_bulk_sku_for_variant_org(
        *,
        product_id: int,
        variant_id: int,
        organization_id: int | None,
    ) -> ProductSKU | None:
        return ProductVariantRouteService.get_base_bulk_sku_for_product(
            product_id=product_id,
            fallback_variant_id=variant_id,
            base_variant_id=variant_id,
            organization_id=organization_id,
        )

    @staticmethod
    def create_variant_and_optional_bulk_sku(
        *,
        product: Product,
        variant_name: str,
        description: str | None,
        organization_id: int | None,
        actor_user_id: int | None,
        auto_create_bulk_sku: bool,
        unit: str,
        default_bulk_label: str,
    ) -> tuple[ProductVariant, ProductSKU | None]:
        new_variant = ProductVariant(
            product_id=product.id,
            name=variant_name,
            description=description,
            organization_id=organization_id,
            created_by=actor_user_id,
        )
        db.session.add(new_variant)

        new_sku = None
        if auto_create_bulk_sku:
            db.session.flush()
            sku_code = ProductService.generate_sku_code(
                product.name, variant_name, default_bulk_label
            )
            sku_name = f"{variant_name} {product.name} ({default_bulk_label})"

            inventory_item = InventoryItem(
                name=f"{product.name} - {variant_name} - {default_bulk_label}",
                type="product",
                unit=unit,
                quantity=0.0,
                organization_id=organization_id,
                created_by=actor_user_id,
            )
            db.session.add(inventory_item)
            db.session.flush()

            new_sku = ProductSKU(
                inventory_item_id=inventory_item.id,
                product_id=product.id,
                variant_id=new_variant.id,
                size_label=default_bulk_label,
                sku_code=sku_code,
                sku=sku_code,
                sku_name=sku_name,
                unit=unit,
                low_stock_threshold=0,
                description=description,
                is_active=True,
                is_product_active=True,
                organization_id=organization_id,
                created_by=actor_user_id,
            )
            db.session.add(new_sku)

        db.session.commit()
        return new_variant, new_sku

    @staticmethod
    def create_variant_with_optional_bulk_sku(
        *,
        product: Product,
        variant_name: str,
        description: str | None,
        organization_id: int | None,
        actor_user_id: int | None,
        auto_create_bulk_sku: bool,
        unit: str,
        default_bulk_label: str,
    ) -> tuple[ProductVariant, ProductSKU | None]:
        return ProductVariantRouteService.create_variant_and_optional_bulk_sku(
            product=product,
            variant_name=variant_name,
            description=description,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            auto_create_bulk_sku=auto_create_bulk_sku,
            unit=unit,
            default_bulk_label=default_bulk_label,
        )

    @staticmethod
    def get_existing_sku_for_variant_size(
        *,
        product_id: int,
        variant_id: int,
        size_label: str,
        organization_id: int | None,
    ) -> ProductSKU | None:
        return (
            ProductSKU.scoped()
            .filter_by(
                product_id=product_id,
                variant_id=variant_id,
                size_label=size_label,
                organization_id=organization_id,
            )
            .first()
        )

    @staticmethod
    def get_existing_sku_for_variant_size_org(
        *,
        product_id: int,
        variant_id: int,
        size_label: str,
        organization_id: int | None,
    ) -> ProductSKU | None:
        return ProductVariantRouteService.get_existing_sku_for_variant_size(
            product_id=product_id,
            variant_id=variant_id,
            size_label=size_label,
            organization_id=organization_id,
        )

    @staticmethod
    def create_sku_for_variant(
        *,
        product: Product,
        variant: ProductVariant,
        size_label: str,
        unit: str,
        low_stock_threshold: str | None,
        organization_id: int | None,
        actor_user_id: int | None,
    ) -> ProductSKU:
        inventory_item = InventoryItem(
            name=f"{product.name} - {variant.name} - {size_label}",
            type="product",
            unit=unit,
            quantity=0.0,
            organization_id=organization_id,
            created_by=actor_user_id,
        )
        db.session.add(inventory_item)
        db.session.flush()

        sku_code = ProductService.generate_sku_code(
            product.name, variant.name, size_label
        )
        new_sku = ProductSKU(
            inventory_item_id=inventory_item.id,
            product_id=product.id,
            variant_id=variant.id,
            size_label=size_label,
            sku_code=sku_code,
            sku=sku_code,
            sku_name=f"{variant.name} {product.name} ({size_label})",
            unit=unit,
            low_stock_threshold=(
                float(low_stock_threshold) if low_stock_threshold else 0
            ),
            organization_id=organization_id,
            created_by=actor_user_id,
            is_active=True,
            is_product_active=True,
        )
        db.session.add(new_sku)
        db.session.commit()
        return new_sku

    @staticmethod
    def find_other_variant_with_name(
        *,
        product_id: int,
        variant_id: int,
        name: str,
    ) -> ProductVariant | None:
        return (
            ProductVariant.scoped()
            .filter(
                ProductVariant.product_id == product_id,
                ProductVariant.name == name,
                ProductVariant.id != variant_id,
            )
            .first()
        )

    @staticmethod
    def get_other_variant_by_name(
        *,
        product_id: int,
        variant_name: str,
        exclude_variant_id: int,
    ) -> ProductVariant | None:
        return ProductVariantRouteService.find_other_variant_with_name(
            product_id=product_id,
            variant_id=exclude_variant_id,
            name=variant_name,
        )

    @staticmethod
    def update_variant_details(
        *,
        variant: ProductVariant,
        name: str,
        description: str | None,
    ) -> None:
        variant.name = name
        variant.description = description
        db.session.commit()

    @staticmethod
    def update_variant(
        *,
        variant: ProductVariant,
        name: str,
        description: str | None,
    ) -> None:
        ProductVariantRouteService.update_variant_details(
            variant=variant,
            name=name,
            description=description,
        )

    @staticmethod
    def mark_variant_and_skus_inactive(
        *,
        variant: ProductVariant,
        skus: list[ProductSKU],
    ) -> None:
        variant.is_active = False
        for sku in skus:
            sku.is_active = False
        db.session.commit()

    @staticmethod
    def deactivate_variant_and_skus(
        *,
        variant: ProductVariant,
        skus: list[ProductSKU],
    ) -> None:
        ProductVariantRouteService.mark_variant_and_skus_inactive(
            variant=variant,
            skus=skus,
        )

    @staticmethod
    def count_active_variants_for_product(*, product_id: int) -> int:
        return (
            ProductVariant.scoped()
            .filter_by(product_id=product_id, is_active=True)
            .count()
        )

    @staticmethod
    def create_default_base_variant(
        *,
        product_id: int,
        organization_id: int | None,
    ) -> ProductVariant:
        base_variant = ProductVariant(
            product_id=product_id,
            name="Base",
            description="Default base variant",
            organization_id=organization_id,
        )
        db.session.add(base_variant)
        db.session.commit()
        return base_variant

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()
