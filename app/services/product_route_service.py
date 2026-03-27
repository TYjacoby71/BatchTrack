"""Product route service boundary.

Synopsis:
Encapsulates product route persistence/query operations so
`app/blueprints/products/products.py` remains transport-focused.
"""

from __future__ import annotations

from app.extensions import db
from app.models import InventoryLot, UnifiedInventoryHistory, UserPreferences
from app.models.product import Product, ProductSKU, ProductVariant


class ProductRouteService:
    """Data/session helpers for product routes."""

    @staticmethod
    def create_inventory_product_item(
        *,
        name: str,
        unit: str,
        organization_id: int | None,
    ):
        from app.models import InventoryItem

        product = InventoryItem(
            name=name,
            type="product",
            unit=unit,
            quantity=0,
            organization_id=organization_id,
        )
        db.session.add(product)
        db.session.flush()
        return product

    @staticmethod
    def create_inventory_product_from_data(*, data: dict, user_type: str | None):
        from app.utils.permissions import get_effective_organization_id

        organization_id = get_effective_organization_id()
        if not organization_id and user_type != "developer":
            raise ValueError("No organization context")

        product = ProductRouteService.create_inventory_product_item(
            name=data["name"],
            unit=data.get("unit", "count"),
            organization_id=organization_id,
        )
        ProductRouteService.commit_session()
        return product

    @staticmethod
    def serialize_created_inventory_product(*, product) -> dict:
        return {
            "success": True,
            "product": {
                "id": product.id,
                "name": product.name,
                "unit": product.unit,
            },
        }

    @staticmethod
    def commit_session() -> None:
        db.session.commit()

    @staticmethod
    def rollback_session() -> None:
        db.session.rollback()

    @staticmethod
    def get_saved_products_sort_preference(*, user_id: int, scope: str) -> str | None:
        prefs = UserPreferences.get_for_user(user_id)
        if not prefs:
            return None
        saved_scope = prefs.get_list_preferences(scope)
        return str(saved_scope.get("sort") or "").strip().lower() or None

    @staticmethod
    def persist_products_sort_preference(
        *,
        user_id: int,
        scope: str,
        sort_type: str,
    ) -> None:
        prefs = UserPreferences.get_for_user(user_id)
        if not prefs:
            return
        current_scope = prefs.get_list_preferences(scope)
        if current_scope.get("sort") == sort_type:
            return
        prefs.set_list_preferences(
            scope,
            {"sort": sort_type},
            merge=True,
        )
        db.session.commit()

    @staticmethod
    def find_product_for_org(*, product_id: int, organization_id: int | None):
        return (
            Product.scoped()
            .filter_by(id=product_id, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def find_product_by_name_for_org(*, name: str, organization_id: int | None):
        return (
            Product.scoped()
            .filter_by(name=name, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def get_product_for_org(*, product_id: int, organization_id: int | None):
        return ProductRouteService.find_product_for_org(
            product_id=product_id,
            organization_id=organization_id,
        )

    @staticmethod
    def find_other_product_with_name_for_org(
        *,
        name: str,
        product_id: int | None = None,
        exclude_product_id: int | None = None,
        organization_id: int | None,
    ):
        effective_exclude_id = (
            exclude_product_id if exclude_product_id is not None else product_id
        )
        return (
            Product.scoped()
            .filter(
                Product.name == name,
                Product.id != effective_exclude_id,
                Product.organization_id == organization_id,
            )
            .first()
        )

    @staticmethod
    def find_legacy_sku_by_product_name_for_org(
        *,
        product_name: str,
        organization_id: int | None,
    ):
        return (
            ProductSKU.scoped()
            .filter_by(product_name=product_name, organization_id=organization_id)
            .first()
        )

    @staticmethod
    def find_first_active_sku_by_product_name_for_org(
        *,
        product_name: str,
        organization_id: int | None,
    ):
        return (
            ProductSKU.scoped()
            .filter_by(
                organization_id=organization_id,
                is_active=True,
            )
            .join(ProductSKU.product)
            .filter(Product.name == product_name)
            .first()
        )

    @staticmethod
    def build_product_summary_payloads(
        *,
        product_data: list[dict],
        organization_id: int | None,
    ) -> list[dict]:
        payloads: list[dict] = []
        for row in product_data:
            product_name = str(row.get("product_name") or "")
            if not product_name:
                continue
            first_sku = (
                ProductRouteService.find_first_active_sku_by_product_name_for_org(
                    product_name=product_name,
                    organization_id=organization_id,
                )
            )
            if not first_sku:
                continue
            payloads.append(
                ProductRouteService._build_product_summary_payload(
                    row=row,
                    product_id=first_sku.product_id,
                    organization_id=organization_id,
                )
            )
        return payloads

    @staticmethod
    def _build_product_summary_payload(
        *,
        row: dict,
        product_id: int | None,
        organization_id: int | None,
    ) -> dict:
        payload = {
            "id": product_id,
            "name": row.get("product_name", ""),
            "total_quantity": float(row.get("total_quantity", 0) or 0),
            "total_bulk": 0.0,
            "total_packaged": 0.0,
            "variant_count": int(row.get("sku_count", 0) or 0),
            "last_updated": row.get("last_updated"),
            "variations": [],
            "inventory": [],
        }
        if not product_id:
            return payload

        product = ProductRouteService.find_product_for_org(
            product_id=product_id,
            organization_id=organization_id,
        )
        if not product:
            return payload

        payload["id"] = product.id
        actual_variants = ProductRouteService.list_active_variants_for_product(
            product_id=product.id
        )
        variant_map: dict[int, dict] = {}
        for variant in actual_variants:
            variation = {
                "name": variant.name,
                "description": variant.description,
                "id": variant.id,
                "sku": None,
                "created_at": variant.created_at,
            }
            payload["variations"].append(variation)
            variant_map[variant.id] = variation

        skus = ProductRouteService.list_active_skus_for_product_for_org(
            product_id=product.id,
            organization_id=organization_id,
        )
        for sku in skus:
            size_label = sku.size_label if sku.size_label else "Bulk"
            quantity = (
                float(sku.inventory_item.quantity or 0.0) if sku.inventory_item else 0.0
            )
            unit = sku.unit or (sku.inventory_item.unit if sku.inventory_item else "")

            variation = variant_map.get(sku.variant_id)
            if not variation and sku.variant:
                variation = {
                    "name": sku.variant.name,
                    "description": sku.variant.description,
                    "id": sku.variant.id,
                    "sku": None,
                    "created_at": sku.variant.created_at,
                }
                payload["variations"].append(variation)
                variant_map[sku.variant_id] = variation

            if variation and not variation.get("sku"):
                variation["sku"] = sku.sku or sku.sku_code

            payload["inventory"].append(
                {
                    "variant": (
                        variation["name"]
                        if variation
                        else (sku.variant.name if sku.variant else "Unassigned")
                    ),
                    "size_label": size_label if size_label else "Bulk",
                    "quantity": quantity,
                    "unit": unit or "",
                    "sku_id": sku.inventory_item_id,
                    "sku_code": sku.sku or sku.sku_code,
                }
            )

            if quantity > 0:
                if size_label.lower() == "bulk":
                    payload["total_bulk"] += quantity
                else:
                    payload["total_packaged"] += quantity

        payload["variant_count"] = len(payload["variations"])
        return payload

    @staticmethod
    def product_name_exists_for_org(*, name: str, organization_id: int | None) -> bool:
        existing_product = ProductRouteService.find_product_by_name_for_org(
            name=name,
            organization_id=organization_id,
        )
        existing_sku = ProductRouteService.find_legacy_sku_by_product_name_for_org(
            product_name=name,
            organization_id=organization_id,
        )
        return bool(existing_product or existing_sku)

    @staticmethod
    def list_active_skus_for_product_for_org(
        *, product_id: int, organization_id: int | None
    ):
        return (
            ProductSKU.scoped()
            .filter_by(
                product_id=product_id,
                is_active=True,
                organization_id=organization_id,
            )
            .all()
        )

    @staticmethod
    def list_active_variants_for_product(*, product_id: int):
        return (
            ProductVariant.scoped()
            .filter_by(product_id=product_id, is_active=True)
            .all()
        )

    @staticmethod
    def find_base_sku_by_inventory_item_for_org(
        *,
        inventory_item_id: int,
        organization_id: int | None,
    ):
        return (
            ProductSKU.scoped()
            .filter_by(
                inventory_item_id=inventory_item_id,
                organization_id=organization_id,
            )
            .first()
        )

    @staticmethod
    def get_base_sku_by_inventory_item_for_org(
        *,
        inventory_item_id: int,
        organization_id: int | None,
    ):
        return ProductRouteService.find_base_sku_by_inventory_item_for_org(
            inventory_item_id=inventory_item_id,
            organization_id=organization_id,
        )

    @staticmethod
    def list_skus_for_product_for_org(*, product_id: int, organization_id: int | None):
        return (
            ProductSKU.scoped()
            .filter_by(
                product_id=product_id,
                organization_id=organization_id,
            )
            .all()
        )

    @staticmethod
    def list_product_skus_for_org(*, product_id: int, organization_id: int | None):
        return ProductRouteService.list_skus_for_product_for_org(
            product_id=product_id,
            organization_id=organization_id,
        )

    @staticmethod
    def list_available_container_items():
        from app.models import InventoryItem

        return (
            InventoryItem.scoped()
            .filter_by(type="container", is_archived=False)
            .filter(InventoryItem.quantity > 0)
            .all()
        )

    @staticmethod
    def list_product_categories():
        from app.models.product_category import ProductCategory

        return ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    @staticmethod
    def apply_category_and_threshold_to_base_sku(
        *,
        base_sku,
        category_id: str | int | None,
        low_stock_threshold: str | float | int | None,
    ) -> None:
        if not base_sku or not base_sku.product:
            return
        base_sku.product.category_id = (
            int(category_id) if category_id is not None else None
        )
        threshold = float(low_stock_threshold) if low_stock_threshold else 0
        base_sku.product.low_stock_threshold = threshold
        base_sku.low_stock_threshold = threshold

    @staticmethod
    def update_product_core_fields(
        *,
        product,
        name: str,
        category_id: str | int | None,
        low_stock_threshold: str | float | int | None,
    ) -> None:
        product.name = name
        if low_stock_threshold is not None:
            product.low_stock_threshold = (
                float(low_stock_threshold) if low_stock_threshold else 0
            )
        try:
            product.category_id = int(category_id)
        except (TypeError, ValueError):
            pass

    @staticmethod
    def delete_product_graph(
        *, product_id: int, sku_inventory_item_ids: list[int]
    ) -> None:
        for inventory_item_id in sku_inventory_item_ids:
            UnifiedInventoryHistory.scoped().filter_by(
                inventory_item_id=inventory_item_id
            ).delete(synchronize_session=False)
            InventoryLot.scoped().filter_by(inventory_item_id=inventory_item_id).delete(
                synchronize_session=False
            )

        ProductSKU.scoped().filter_by(product_id=product_id).delete()
        ProductVariant.scoped().filter_by(product_id=product_id).delete()
        Product.scoped().filter_by(id=product_id).delete()

    @staticmethod
    def delete_product_hierarchy(*, product_id: int, skus: list) -> None:
        sku_inventory_item_ids = [sku.inventory_item_id for sku in skus]
        ProductRouteService.delete_product_graph(
            product_id=product_id,
            sku_inventory_item_ids=sku_inventory_item_ids,
        )
