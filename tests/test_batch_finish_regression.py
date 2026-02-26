import pytest
from flask_login import login_user

from app.extensions import db
from app.models import (
    Batch,
    InventoryItem,
    Product,
    ProductCategory,
    ProductSKU,
    ProductVariant,
    Recipe,
)
from app.models.models import User
from app.services.batch_service.batch_operations import BatchOperationsService
from app.services.product_service import ProductService


def _setup_recipe_for_user(user, name: str, label_prefix: str) -> Recipe:
    category = ProductCategory.query.filter_by(name="Uncategorized").first()
    recipe = Recipe(
        name=name,
        label_prefix=label_prefix,
        category_id=category.id,
        organization_id=user.organization_id,
        created_by=user.id,
    )
    db.session.add(recipe)
    db.session.flush()
    return recipe


@pytest.mark.usefixtures("app_context")
def test_complete_batch_surfaces_adjustment_failure_for_ingredient(app, monkeypatch):
    """Finish should fail instead of flashing success when inventory credit fails."""
    with app.test_request_context("/"):
        user = User.query.first()
        login_user(user)

        recipe = _setup_recipe_for_user(user, "Intermediate Failure Recipe", "INTFAIL")
        batch = Batch(
            recipe_id=recipe.id,
            label_code="INTFAIL-001",
            batch_type="ingredient",
            status="in_progress",
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(batch)
        db.session.commit()

        from app.blueprints.batches import finish_batch as finish_batch_module

        monkeypatch.setattr(
            finish_batch_module,
            "process_inventory_adjustment",
            lambda **kwargs: (False, "forced adjustment failure"),
        )

        success, message = BatchOperationsService.complete_batch(
            batch.id,
            {"output_type": "ingredient", "final_quantity": "8", "output_unit": "oz"},
        )

        db.session.refresh(batch)
        assert success is False
        assert "forced adjustment failure" in message
        assert batch.status == "in_progress"


@pytest.mark.usefixtures("app_context")
def test_complete_batch_fails_when_portion_credit_fails(app, monkeypatch):
    """Portion SKU credit errors must fail completion (not silently succeed)."""
    with app.test_request_context("/"):
        user = User.query.first()
        login_user(user)

        category = ProductCategory.query.filter_by(name="Uncategorized").first()
        recipe = _setup_recipe_for_user(user, "Portion Failure Recipe", "PRTFAIL")
        product = Product(
            name="Portion Failure Product",
            category_id=category.id,
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(product)
        db.session.flush()
        variant = ProductVariant(
            product_id=product.id,
            name="Base",
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(variant)
        db.session.flush()

        batch = Batch(
            recipe_id=recipe.id,
            label_code="PRTFAIL-001",
            batch_type="product",
            status="in_progress",
            organization_id=user.organization_id,
            created_by=user.id,
            is_portioned=True,
            portion_name="Bar",
        )
        db.session.add(batch)
        db.session.commit()

        from app.blueprints.batches import finish_batch as finish_batch_module

        monkeypatch.setattr(
            finish_batch_module,
            "process_inventory_adjustment",
            lambda **kwargs: (False, "forced portion credit failure"),
        )

        success, message = BatchOperationsService.complete_batch(
            batch.id,
            {
                "output_type": "product",
                "product_id": product.id,
                "variant_id": variant.id,
                "final_quantity": "4",
                "output_unit": "oz",
                "final_portions": "8",
            },
        )

        db.session.refresh(batch)
        assert success is False
        assert "forced portion credit failure" in message
        assert batch.status == "in_progress"


@pytest.mark.usefixtures("app_context")
def test_complete_batch_creates_separate_bulk_sku_for_incompatible_unit(app):
    """If existing Bulk unit is incompatible, completion should create a new Bulk SKU."""
    with app.test_request_context("/"):
        user = User.query.first()
        login_user(user)

        category = ProductCategory.query.filter_by(name="Uncategorized").first()
        recipe = _setup_recipe_for_user(user, "Bulk Unit Rebase Recipe", "BULKREB")
        product = Product(
            name="Bulk Unit Rebase Product",
            category_id=category.id,
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(product)
        db.session.flush()
        variant = ProductVariant(
            product_id=product.id,
            name="Base",
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(variant)
        db.session.flush()
        db.session.commit()

        # Existing Bulk SKU in incompatible unit.
        legacy_bulk_sku = ProductService.get_or_create_sku(
            product_name=product.name,
            variant_name=variant.name,
            size_label="Bulk",
            unit="oz",
        )
        legacy_bulk_sku.inventory_item.quantity = 0.0
        db.session.commit()
        assert legacy_bulk_sku.inventory_item.unit == "oz"

        batch = Batch(
            recipe_id=recipe.id,
            label_code="BULKREB-001",
            batch_type="product",
            status="in_progress",
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(batch)
        db.session.commit()

        success, message = BatchOperationsService.complete_batch(
            batch.id,
            {
                "output_type": "product",
                "product_id": product.id,
                "variant_id": variant.id,
                "final_quantity": "12",
                "output_unit": "floz",
            },
        )

        db.session.refresh(batch)
        assert success is True, f"Complete batch failed unexpectedly: {message}"
        assert batch.status == "completed"

        refreshed_bulk_skus = ProductSKU.query.filter_by(
            product_id=product.id, variant_id=variant.id
        ).filter(ProductSKU.size_label.ilike("Bulk%")).all()
        assert len(refreshed_bulk_skus) >= 2
        units = {sku.unit for sku in refreshed_bulk_skus}
        assert "oz" in units
        assert "floz" in units
        size_labels = {sku.size_label for sku in refreshed_bulk_skus}
        assert "Bulk Weight" in size_labels
        assert "Bulk Volume" in size_labels


@pytest.mark.usefixtures("app_context")
def test_complete_batch_forces_ingredient_output_when_product_creation_locked(
    app, monkeypatch
):
    """Product output payloads should complete as ingredients when products.create is unavailable."""
    with app.test_request_context("/"):
        user = User.query.first()
        login_user(user)

        recipe = _setup_recipe_for_user(
            user, "Permission Locked Product Batch", "LOCKED"
        )
        batch = Batch(
            recipe_id=recipe.id,
            label_code="LOCKED-001",
            batch_type="product",
            status="in_progress",
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(batch)
        db.session.commit()

        from app.blueprints.batches import finish_batch as finish_batch_module

        def _permission_gate(_user, permission_name):
            if permission_name == "products.create":
                return False
            return True

        monkeypatch.setattr(finish_batch_module, "has_permission", _permission_gate)

        success, message = BatchOperationsService.complete_batch(
            batch.id,
            {"output_type": "product", "final_quantity": "6", "output_unit": "oz"},
        )

        db.session.refresh(batch)
        assert success is True, f"Complete batch failed unexpectedly: {message}"
        assert batch.status == "completed"

        intermediate_item = InventoryItem.query.filter_by(
            name=f"{recipe.name} (Intermediate)", organization_id=user.organization_id
        ).first()
        assert intermediate_item is not None

        sku_count = ProductSKU.query.filter_by(
            organization_id=user.organization_id
        ).count()
        assert sku_count == 0


@pytest.mark.usefixtures("app_context")
def test_complete_batch_untracked_mode_skips_output_inventory_posting(app, monkeypatch):
    """When org tier disables output tracking, completion records details only."""
    with app.test_request_context("/"):
        user = User.query.first()
        login_user(user)

        recipe = _setup_recipe_for_user(user, "Untracked Output Recipe", "UNTRK")
        batch = Batch(
            recipe_id=recipe.id,
            label_code="UNTRK-001",
            batch_type="product",
            status="in_progress",
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(batch)
        db.session.commit()

        from app.blueprints.batches import finish_batch as finish_batch_module

        def _tier_gate(permission_name, **kwargs):
            if permission_name == "batches.track_inventory_outputs":
                return False
            return True

        monkeypatch.setattr(finish_batch_module, "has_tier_permission", _tier_gate)
        monkeypatch.setattr(
            finish_batch_module,
            "_create_intermediate_ingredient",
            lambda *args, **kwargs: pytest.fail(
                "Intermediate output should not be created in untracked mode"
            ),
        )
        monkeypatch.setattr(
            finish_batch_module,
            "_create_product_output",
            lambda *args, **kwargs: pytest.fail(
                "Product output should not be created in untracked mode"
            ),
        )

        success, message = BatchOperationsService.complete_batch(
            batch.id,
            {"output_type": "product", "final_quantity": "9", "output_unit": "oz"},
        )

        db.session.refresh(batch)
        assert success is True, f"Complete batch failed unexpectedly: {message}"
        assert batch.status == "completed"
        assert batch.batch_type == "untracked"

        intermediate_item = InventoryItem.query.filter_by(
            name=f"{recipe.name} (Intermediate)", organization_id=user.organization_id
        ).first()
        assert intermediate_item is None
