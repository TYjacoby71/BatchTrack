import pytest
from flask_login import login_user

from app.extensions import db
from app.models import Product, ProductSKU, ProductVariant
from app.models.batch import Batch, BatchIngredient
from app.models.inventory import InventoryItem
from app.models.models import User
from app.models.product_category import ProductCategory
from app.models.recipe import Recipe
from app.models.unit import Unit
from app.services.batch_service.batch_operations import BatchOperationsService
from app.services.production_planning.service import PlanProductionService
from app.services.recipe_service._core import create_recipe


@pytest.mark.usefixtures("app_context")
def test_portioning_sku_labels_differ(client):
    # Seed category and count units
    soaps = ProductCategory(name="Soaps", is_typically_portioned=True)
    db.session.add(soaps)
    if not Unit.query.filter_by(name="Piece").first():
        db.session.add(
            Unit(
                name="Piece",
                unit_type="count",
                conversion_factor=1.0,
                base_unit="Piece",
                is_active=True,
                is_custom=False,
                is_mapped=True,
            )
        )
    if not Unit.query.filter_by(name="oz").first():
        db.session.add(
            Unit(
                name="oz",
                unit_type="weight",
                conversion_factor=1.0,
                base_unit="oz",
                is_active=True,
                is_custom=False,
                is_mapped=True,
            )
        )
    if not Unit.query.filter_by(name="lb").first():
        db.session.add(
            Unit(
                name="lb",
                unit_type="weight",
                conversion_factor=16.0,
                base_unit="oz",
                is_active=True,
                is_custom=False,
                is_mapped=True,
            )
        )
    db.session.commit()

    # Create product and variant
    product = Product(name="Salt Soap", category_id=soaps.id)
    db.session.add(product)
    db.session.flush()
    variant = ProductVariant(product_id=product.id, name="Lavender")
    db.session.add(variant)
    db.session.commit()

    # Create portioned recipe (5 lb bulk, 10 portions)
    ok, recipe = create_recipe(
        name="Salt Soap Base - Lavender",
        instructions="Mix and pour",
        yield_amount=0,
        yield_unit="",
        ingredients=[],
        allowed_containers=[],
        label_prefix="SOAP",
        category_id=soaps.id,
        portioning_data={
            "is_portioned": True,
            "portion_count": 10,
            "portion_name": "Bar",
            "bulk_yield_quantity": 5.0,
            "bulk_yield_unit_id": Unit.query.filter_by(name="lb").first().id,
        },
        status="draft",
    )
    assert ok, f"Failed to create recipe: {recipe}"

    # Start batch
    snapshot = PlanProductionService.build_plan(
        recipe=recipe,
        scale=1.0,
        batch_type="product",
        notes="Test batch",
        containers=[],
    )
    batch, errs = BatchOperationsService.start_batch(snapshot.to_dict())
    assert batch is not None, f"Start batch failed: {errs}"

    # Finish batch with 5 lb final bulk and 10 portions
    resp_ok, msg = BatchOperationsService.complete_batch(
        batch.id,
        {
            "output_type": "product",
            "product_id": product.id,
            "variant_id": variant.id,
            "final_quantity": "5",
            "output_unit": "lb",
            "final_portions": "10",
        },
    )
    assert resp_ok, f"Complete batch failed: {msg}"

    sku_a = (
        ProductSKU.query.filter_by(product_id=product.id, variant_id=variant.id)
        .order_by(ProductSKU.id.desc())
        .first()
    )
    assert sku_a is not None
    size_a = sku_a.size_label
    assert "Bar" in size_a
    # Soaps template should render sku_name with size_label
    assert "Salt Soap" in sku_a.sku_name
    assert "Lavender" in sku_a.sku_name
    assert "(" in sku_a.sku_name and ")" in sku_a.sku_name

    # Start second batch
    snapshot2 = PlanProductionService.build_plan(
        recipe=recipe,
        scale=1.0,
        batch_type="product",
        notes="Test batch 2",
        containers=[],
    )
    batch2, errs2 = BatchOperationsService.start_batch(snapshot2.to_dict())
    assert batch2 is not None, f"Start batch2 failed: {errs2}"

    # Finish second batch with 5 lb final bulk but 20 portions
    resp_ok2, msg2 = BatchOperationsService.complete_batch(
        batch2.id,
        {
            "output_type": "product",
            "product_id": product.id,
            "variant_id": variant.id,
            "final_quantity": "5",
            "output_unit": "lb",
            "final_portions": "20",
        },
    )
    assert resp_ok2, f"Complete batch2 failed: {msg2}"

    sku_b = (
        ProductSKU.query.filter_by(product_id=product.id, variant_id=variant.id)
        .order_by(ProductSKU.id.desc())
        .first()
    )
    assert sku_b is not None
    size_b = sku_b.size_label

    assert size_a != size_b, f"Expected different size labels, got {size_a} == {size_b}"
    assert sku_a.sku_name != sku_b.sku_name


@pytest.mark.usefixtures("app_context")
def test_portion_costing_uses_portion_count(app):
    """Portioned batch inventory should divide total cost by actual portion output."""
    with app.test_request_context("/"):
        user = User.query.first()
        login_user(user)

        org_id = user.organization_id
        category = ProductCategory.query.filter_by(name="Uncategorized").first()

        # Core product/variant scaffolding
        product = Product(
            name="Portioned Product",
            category_id=category.id,
            organization_id=org_id,
            created_by=user.id,
        )
        variant = ProductVariant(
            product=product, name="Classic", organization_id=org_id, created_by=user.id
        )
        recipe = Recipe(
            name="Portioned Recipe",
            label_prefix="PORT",
            category_id=category.id,
            organization_id=org_id,
            created_by=user.id,
            is_portioned=True,
            portion_name="Bar",
            portion_count=4,
        )
        ingredient = InventoryItem(
            name="Olive Oil",
            type="ingredient",
            unit="kg",
            quantity=0.0,
            cost_per_unit=3.0,
            organization_id=org_id,
            created_by=user.id,
        )

        db.session.add_all([product, variant, recipe, ingredient])
        db.session.flush()

        batch = Batch(
            recipe_id=recipe.id,
            label_code="PORT-TEST",
            batch_type="product",
            status="in_progress",
            organization_id=org_id,
            created_by=user.id,
            is_portioned=True,
            portion_name="Bar",
        )
        db.session.add(batch)
        db.session.flush()

        snapshot = BatchIngredient(
            batch_id=batch.id,
            inventory_item_id=ingredient.id,
            quantity_used=4.0,
            unit="kg",
            cost_per_unit=3.0,
            organization_id=org_id,
        )
        db.session.add(snapshot)
        db.session.commit()

        # Sanity check: snapshot captured expected cost basis
        assert len(batch.batch_ingredients) == 1
        material_cost = sum(
            (ing.quantity_used or 0) * (ing.cost_per_unit or 0)
            for ing in batch.batch_ingredients
        )
        assert material_cost == pytest.approx(12.0)

        success, message = BatchOperationsService.complete_batch(
            batch.id,
            {
                "output_type": "product",
                "product_id": product.id,
                "variant_id": variant.id,
                "final_quantity": "1",  # Deliberately not equal to portions to catch regression
                "output_unit": "kg",
                "final_portions": "4",
            },
        )
        assert success, f"Complete batch failed: {message}"

        portion_sku = (
            ProductSKU.query.filter_by(product_id=product.id, variant_id=variant.id)
            .order_by(ProductSKU.id.desc())
            .first()
        )
        assert portion_sku is not None
        from app.models.inventory_lot import InventoryLot

        lots = InventoryLot.query.filter_by(
            inventory_item_id=portion_sku.inventory_item_id
        ).all()
        assert lots, "Portion SKU should have at least one FIFO lot"
        assert lots[0].unit_cost == pytest.approx(3.0)
        from app.services.costing_engine import weighted_average_cost_for_item

        assert weighted_average_cost_for_item(
            portion_sku.inventory_item_id
        ) == pytest.approx(3.0)
        assert portion_sku.inventory_item.cost_per_unit == pytest.approx(3.0)
