"""Test data seeder for demo scenarios.

Synopsis:
Seeds a rich dataset for end-to-end inventory and batch workflows.

Glossary:
- Seeder: Script that inserts baseline or demo data.
- Living dataset: Realistic data used for manual QA.
"""

from datetime import timedelta
from datetime import timezone as dt_timezone
from typing import Dict, List, Optional

from ..extensions import db
from ..models import (
    Batch,
    BatchConsumable,
    BatchContainer,
    BatchIngredient,
    BatchTimer,
    ExtraBatchConsumable,
    ExtraBatchContainer,
    ExtraBatchIngredient,
    IngredientCategory,
    InventoryItem,
    InventoryLot,
    Organization,
    Product,
    ProductCategory,
    ProductSKU,
    ProductVariant,
    Recipe,
    RecipeIngredient,
    Reservation,
    UnifiedInventoryHistory,
    Unit,
    User,
)
from ..models.global_item import GlobalItem
from ..services.inventory_adjustment import process_inventory_adjustment
from ..services.unit_conversion import ConversionEngine
from ..utils.timezone_utils import TimezoneUtils


# --- Seed test data ---
# Purpose: Seed a living dataset for QA workflows.
def seed_test_data(organization_id: Optional[int] = None):
    """Seed a rich "living" dataset for a milk & honey workflow using core services."""

    if organization_id is None:
        org = Organization.query.first()
        if not org:
            print("❌ No organization found! Run user seeder first.")
            return
        organization_id = org.id

    admin_user = User.query.filter_by(username="admin").first()
    if not admin_user:
        print("❌ Admin user not found! Run user seeder first.")
        return

    now = TimezoneUtils.utc_now()
    print("=== Seeding Living Account Test Data ===")

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------
    def ensure_unit(
        name: str, symbol: str, unit_type: str, base_unit: str, conversion_factor: float
    ):
        unit = Unit.query.filter_by(name=name).first()
        if not unit:
            unit = Unit(
                name=name,
                symbol=symbol,
                unit_type=unit_type,
                base_unit=base_unit,
                conversion_factor=conversion_factor,
                is_custom=False,
                is_mapped=True,
                created_by=admin_user.id,
                organization_id=None,
            )
            db.session.add(unit)
            db.session.flush()
            print(f"   ➕ Added unit '{name}'")
        return unit

    def get_or_create_category(name: str) -> IngredientCategory:
        category = IngredientCategory.query.filter_by(
            name=name, organization_id=organization_id
        ).first()
        if not category:
            category = IngredientCategory(name=name, organization_id=organization_id)
            db.session.add(category)
            db.session.flush()
            print(f"   ➕ Created ingredient category '{name}'")
        return category

    def ensure_global_item(name: str, item_type: str, **kwargs) -> GlobalItem:
        global_item = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
        if not global_item:
            global_item = GlobalItem(name=name, item_type=item_type, **kwargs)
            db.session.add(global_item)
            db.session.flush()
            print(f"   🌐 Registered global item '{name}' ({item_type})")
        return global_item

    def reset_inventory_item(item: InventoryItem):
        UnifiedInventoryHistory.query.filter_by(inventory_item_id=item.id).delete(
            synchronize_session=False
        )
        InventoryLot.query.filter_by(inventory_item_id=item.id).delete(
            synchronize_session=False
        )
        from app.services.quantity_base import sync_item_quantity_from_base

        item.quantity_base = 0
        sync_item_quantity_from_base(item)
        db.session.flush()

    def remove_existing_batches(labels: List[str]):
        for label in labels:
            batch = Batch.query.filter_by(
                label_code=label, organization_id=organization_id
            ).first()
            if not batch:
                continue
            UnifiedInventoryHistory.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            BatchIngredient.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            BatchContainer.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            BatchConsumable.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            ExtraBatchIngredient.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            ExtraBatchContainer.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            ExtraBatchConsumable.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            BatchTimer.query.filter_by(batch_id=batch.id).delete(
                synchronize_session=False
            )
            db.session.delete(batch)
        db.session.flush()

    def process_adjustment(context: str, **kwargs):
        response = process_inventory_adjustment(**kwargs)
        if isinstance(response, tuple):
            success = response[0]
            message = response[1] if len(response) > 1 else ""
        else:
            success = bool(response)
            message = ""
        if not success:
            raise RuntimeError(f"{context} failed: {message}")
        return response

    def convert_units(
        amount: float, from_unit: str, to_unit: str, ingredient: InventoryItem
    ) -> float:
        conversion = ConversionEngine.convert_units(
            amount,
            from_unit,
            to_unit,
            ingredient_id=ingredient.id,
            density=ingredient.density
            or (ingredient.category.default_density if ingredient.category else None),
            organization_id=organization_id,
        )
        if not conversion.get("success") or conversion.get("converted_value") is None:
            raise RuntimeError(
                f"Unit conversion failed for {ingredient.name}: {conversion.get('error_code')}"
            )
        return conversion["converted_value"]

    def update_history_timestamp(
        item_id: int,
        change_type: str,
        timestamp,
        notes_contains: Optional[str] = None,
        batch_id: Optional[int] = None,
    ):
        query = UnifiedInventoryHistory.query.filter_by(
            inventory_item_id=item_id, change_type=change_type
        )
        if batch_id is not None:
            query = query.filter_by(batch_id=batch_id)
        entries = query.all()
        for entry in entries:
            if notes_contains and notes_contains not in (entry.notes or ""):
                continue
            entry.timestamp = timestamp

    def update_lot_dates(
        lot: InventoryLot,
        received_at,
        expiration_at=None,
        source_notes: Optional[str] = None,
    ):
        lot.received_date = received_at
        lot.created_at = received_at
        if expiration_at is not None:
            lot.expiration_date = expiration_at
        if source_notes is not None:
            lot.source_notes = source_notes
        history_entries = UnifiedInventoryHistory.query.filter_by(
            affected_lot_id=lot.id
        ).all()
        for entry in history_entries:
            entry.timestamp = received_at
            if expiration_at is not None:
                entry.expiration_date = expiration_at
            if source_notes is not None:
                entry.notes = source_notes

    def normalize_timestamp(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(dt_timezone.utc).replace(tzinfo=None)

    total_lots_created = 0

    # ------------------------------------------------------------------
    # Ensure reference data exists
    # ------------------------------------------------------------------
    ensure_unit("cup", "cup", "volume", "ml", 236.588)
    ensure_unit("cl", "cL", "volume", "ml", 10.0)

    categories = {
        name: get_or_create_category(name)
        for name in ["Dairy", "Syrups", "Container", "Other"]
    }

    beverage_category = ProductCategory.query.filter_by(name="Beverages").first()
    if not beverage_category:
        beverage_category = ProductCategory(
            name="Beverages",
            is_typically_portioned=False,
            sku_name_template="{variant} {product} ({container})",
            skin_enabled=False,
        )
        db.session.add(beverage_category)
        db.session.flush()
        print("   ➕ Created product category 'Beverages'")

    # ------------------------------------------------------------------
    # Inventory item configuration
    # ------------------------------------------------------------------
    inventory_plan = [
        {
            "key": "milk",
            "name": "Whole Milk",
            "type": "ingredient",
            "unit": "gallon",
            "cost_per_unit": 4.95,
            "category": categories["Dairy"],
            "density": 1.03,
            "is_perishable": True,
            "shelf_life_days": 7,
            "global_item": {
                "item_type": "ingredient",
                "density": 1.03,
                "default_unit": "gallon",
                "ingredient_category_id": categories["Dairy"].id,
                "recommended_shelf_life_days": 7,
            },
            "lots": [
                {
                    "quantity": 2.5,
                    "unit_cost": 4.75,
                    "days_ago": 32,
                    "notes": "Opening month delivery",
                    "expired": True,
                },
                {
                    "quantity": 3.0,
                    "unit_cost": 4.95,
                    "days_ago": 6,
                    "notes": "Weekly restock from local dairy",
                },
                {
                    "quantity": 3.0,
                    "unit_cost": 5.05,
                    "days_ago": 2,
                    "notes": "Fresh restock pending current batch",
                },
            ],
        },
        {
            "key": "honey",
            "name": "Wildflower Honey",
            "type": "ingredient",
            "unit": "lb",
            "cost_per_unit": 3.85,
            "category": categories["Syrups"],
            "density": 1.42,
            "is_perishable": True,
            "shelf_life_days": 540,
            "global_item": {
                "item_type": "ingredient",
                "density": 1.42,
                "default_unit": "lb",
                "ingredient_category_id": categories["Syrups"].id,
                "recommended_shelf_life_days": 540,
            },
            "lots": [
                {
                    "quantity": 50.0,
                    "unit_cost": 3.45,
                    "days_ago": 210,
                    "notes": "Legacy drum now empty",
                    "expired": True,
                },
                {
                    "quantity": 60.0,
                    "unit_cost": 3.75,
                    "days_ago": 45,
                    "notes": "Summer harvest purchase",
                },
                {
                    "quantity": 60.0,
                    "unit_cost": 3.95,
                    "days_ago": 8,
                    "notes": "Recent cooperative delivery",
                },
            ],
        },
        {
            "key": "container",
            "name": "4 fl oz Boston Round Bottle",
            "type": "container",
            "unit": "count",
            "cost_per_unit": 0.82,
            "category": categories["Container"],
            "density": None,
            "is_perishable": False,
            "shelf_life_days": None,
            "container_material": "Glass",
            "container_style": "Boston Round",
            "container_type": "Bottle",
            "capacity": 4.0,
            "capacity_unit": "floz",
            "global_item": {
                "item_type": "container",
                "capacity": 4.0,
                "capacity_unit": "floz",
                "container_material": "Glass",
                "container_style": "Boston Round",
                "container_type": "Bottle",
            },
            "lots": [
                {
                    "quantity": 120,
                    "unit_cost": 0.8,
                    "days_ago": 35,
                    "notes": "Bulk glass pallet",
                },
                {
                    "quantity": 80,
                    "unit_cost": 0.84,
                    "days_ago": 7,
                    "notes": "Top off order for autumn promotions",
                },
                {
                    "quantity": 40,
                    "remaining_quantity": 0,
                    "unit_cost": 0.86,
                    "days_ago": 52,
                    "notes": "Legacy lot fully consumed",
                    "expired": True,
                },
            ],
        },
    ]

    inventory_items: Dict[str, InventoryItem] = {}

    for spec in inventory_plan:
        item = InventoryItem.query.filter_by(
            name=spec["name"], organization_id=organization_id
        ).first()
        if not item:
            item = InventoryItem(
                name=spec["name"],
                unit=spec["unit"],
                type=spec["type"],
                cost_per_unit=spec["cost_per_unit"],
                category_id=spec["category"].id if spec["category"] else None,
                density=spec.get("density"),
                is_perishable=spec.get("is_perishable", False),
                shelf_life_days=spec.get("shelf_life_days"),
                capacity=spec.get("capacity"),
                capacity_unit=spec.get("capacity_unit"),
                container_material=spec.get("container_material"),
                container_style=spec.get("container_style"),
                container_type=spec.get("container_type"),
                organization_id=organization_id,
                created_by=admin_user.id,
            )
            db.session.add(item)
            db.session.flush()
        else:
            item.unit = spec["unit"]
            item.type = spec["type"]
            item.cost_per_unit = spec["cost_per_unit"]
            item.category_id = spec["category"].id if spec["category"] else None
            item.density = spec.get("density")
            item.is_perishable = spec.get("is_perishable", False)
            item.shelf_life_days = spec.get("shelf_life_days")
            item.capacity = spec.get("capacity")
            item.capacity_unit = spec.get("capacity_unit")
            item.container_material = spec.get("container_material")
            item.container_style = spec.get("container_style")
            item.container_type = spec.get("container_type")

        reset_inventory_item(item)

        global_meta = spec.get("global_item")
        if global_meta:
            global_item = ensure_global_item(
                spec["name"], global_meta.pop("item_type"), **global_meta
            )
            item.global_item_id = global_item.id
            item.reference_item_name = global_item.name

        inventory_items[spec["key"]] = item

    db.session.commit()

    print("→ Restocking ingredient and container lots via adjustment service...")

    # Create all lots in chronological order (oldest first)
    all_lot_operations = []
    for spec in inventory_plan:
        item = inventory_items[spec["key"]]
        for lot_spec in spec["lots"]:
            received_at = now - timedelta(days=lot_spec.get("days_ago", 0))
            all_lot_operations.append(
                {
                    "item": item,
                    "spec": lot_spec,
                    "received_at": received_at,
                    "operation_type": "restock",
                }
            )

    # Sort by timestamp (oldest first) to ensure chronological order
    all_lot_operations.sort(key=lambda x: x["received_at"])

    # Execute lot creation operations in chronological order
    for operation in all_lot_operations:
        item = operation["item"]
        lot_spec = operation["spec"]
        received_at = operation["received_at"]

        process_adjustment(
            context=f"Restock {item.name}",
            item_id=item.id,
            change_type="restock",
            quantity=float(lot_spec["quantity"]),
            unit=item.unit,
            notes=lot_spec.get("notes"),
            cost_override=lot_spec.get("unit_cost"),
            created_by=admin_user.id,
            defer_commit=True,
        )
        db.session.flush()
        new_lot = (
            InventoryLot.query.filter_by(inventory_item_id=item.id)
            .order_by(InventoryLot.id.desc())
            .first()
        )
        expiration = None
        if lot_spec.get("expired"):
            expiration = received_at + timedelta(days=1)
        elif item.is_perishable and item.shelf_life_days:
            expiration = received_at + timedelta(days=item.shelf_life_days)
        update_lot_dates(
            new_lot,
            received_at,
            expiration_at=expiration,
            source_notes=lot_spec.get("notes"),
        )
        total_lots_created += 1
        db.session.commit()

    # ------------------------------------------------------------------
    # Recipe configuration
    # ------------------------------------------------------------------
    container_item = inventory_items["container"]
    honey_item = inventory_items["honey"]
    milk_item = inventory_items["milk"]

    recipe_name = "Milk & Honey Elixir"
    recipe = Recipe.query.filter_by(
        name=recipe_name, organization_id=organization_id
    ).first()
    if not recipe:
        recipe = Recipe(
            name=recipe_name,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(recipe)

    recipe.instructions = "Warm milk to 120F, dissolve honey, blend until uniform, cool, and bottle immediately."
    recipe.predicted_yield = 4.0
    recipe.predicted_yield_unit = "floz"
    recipe.is_portioned = False
    recipe.portioning_data = None
    recipe.allowed_containers = [container_item.id]
    recipe.category_id = beverage_category.id

    for assoc in list(recipe.recipe_ingredients):
        db.session.delete(assoc)

    recipe_ingredients = [
        {"item": honey_item, "quantity": 1.0, "unit": "cup", "order": 0},
        {"item": milk_item, "quantity": 10.0, "unit": "cl", "order": 1},
    ]

    for ingredient_data in recipe_ingredients:
        recipe_ingredient = RecipeIngredient(
            recipe=recipe,
            inventory_item_id=ingredient_data["item"].id,
            quantity=ingredient_data["quantity"],
            unit=ingredient_data["unit"],
            order_position=ingredient_data["order"],
            organization_id=organization_id,
        )
        db.session.add(recipe_ingredient)

    db.session.commit()
    print("→ Recipe configured with system ingredients and containers")

    # ------------------------------------------------------------------
    # Finished goods inventory, product, and SKU
    # ------------------------------------------------------------------
    product_item_key = "product"
    product_inventory_name = "Milk & Honey Elixir (Finished)"
    product_item = InventoryItem.query.filter_by(
        name=product_inventory_name, organization_id=organization_id
    ).first()
    if not product_item:
        product_item = InventoryItem(
            name=product_inventory_name,
            unit="unit",
            type="product",
            cost_per_unit=7.5,
            category_id=categories["Other"].id,
            is_perishable=True,
            shelf_life_days=45,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(product_item)
        db.session.flush()
    else:
        product_item.unit = "unit"
        product_item.type = "product"
        product_item.cost_per_unit = 7.5
        product_item.category_id = categories["Other"].id
        product_item.is_perishable = True
        product_item.shelf_life_days = 45

    reset_inventory_item(product_item)
    inventory_items[product_item_key] = product_item

    product = Product.query.filter_by(
        name="Milk & Honey Elixir", organization_id=organization_id
    ).first()
    if not product:
        product = Product(
            name="Milk & Honey Elixir",
            description="Gently warmed whole milk blended with raw wildflower honey.",
            category_id=beverage_category.id,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(product)
        db.session.flush()

    variant = ProductVariant.query.filter_by(
        product_id=product.id, name="Original"
    ).first()
    if not variant:
        variant = ProductVariant(
            product_id=product.id,
            name="Original",
            description="Classic formulation",
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(variant)
        db.session.flush()

    product_sku = ProductSKU.query.filter_by(inventory_item_id=product_item.id).first()
    if not product_sku:
        product_sku = ProductSKU(
            inventory_item_id=product_item.id,
            product_id=product.id,
            variant_id=variant.id,
            size_label="4 fl oz",
            sku="MH-ELIXIR-4OZ",
            sku_code="MH-ELIXIR-4OZ",
            sku_name="Milk & Honey Elixir 4 fl oz",
            unit="unit",
            retail_price=14.0,
            wholesale_price=9.5,
            low_stock_threshold=12,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(product_sku)
    else:
        product_sku.product_id = product.id
        product_sku.variant_id = variant.id
        product_sku.size_label = "4 fl oz"
        product_sku.sku = "MH-ELIXIR-4OZ"
        product_sku.sku_code = "MH-ELIXIR-4OZ"
        product_sku.sku_name = "Milk & Honey Elixir 4 fl oz"
        product_sku.unit = "unit"
        product_sku.retail_price = 14.0
        product_sku.wholesale_price = 9.5
        product_sku.low_stock_threshold = 12

    db.session.commit()
    print("→ Product and SKU ready for finished goods")

    # ------------------------------------------------------------------
    # Batch history (consumption + finished goods lots)
    # ------------------------------------------------------------------
    batch_plan = [
        {
            "label_code": "MH-240901",
            "scale": 40,
            "status": "completed",
            "started_days_ago": 34,
            "completed_days_ago": 33,
            "final_quantity": 40,
            "remaining_quantity": 0,
            "notes": "Pilot production for wholesale tastings",
            "unit_cost": 6.8,
        },
        {
            "label_code": "MH-240915",
            "scale": 50,
            "status": "completed",
            "started_days_ago": 20,
            "completed_days_ago": 19,
            "final_quantity": 50,
            "remaining_quantity": 0,
            "notes": "Market release run fulfilling co-op orders",
            "unit_cost": 6.7,
        },
        {
            "label_code": "MH-241001",
            "scale": 60,
            "status": "completed",
            "started_days_ago": 6,
            "completed_days_ago": 5,
            "final_quantity": 60,
            "remaining_quantity": 10,
            "notes": "Bulk run ahead of holiday demand",
            "unit_cost": 6.65,
        },
        {
            "label_code": "MH-Current",
            "scale": 25,
            "status": "in_progress",
            "started_days_ago": 1,
            "completed_days_ago": None,
            "final_quantity": None,
            "remaining_quantity": None,
            "notes": "Current batch staged and heating",
        },
    ]

    remove_existing_batches([plan["label_code"] for plan in batch_plan])
    db.session.commit()

    batches_by_label: Dict[str, Batch] = {}
    completed_batch_count = 0
    in_progress_batch_count = 0

    ingredient_map = {
        assoc.inventory_item_id: assoc for assoc in recipe.recipe_ingredients
    }

    # Sort batch plan by start date (oldest first) for chronological processing
    sorted_batch_plan = sorted(
        batch_plan, key=lambda x: x["started_days_ago"], reverse=True
    )

    for plan in sorted_batch_plan:
        started_at = normalize_timestamp(now - timedelta(days=plan["started_days_ago"]))
        completed_at = None
        if plan.get("completed_days_ago") is not None:
            completed_at = normalize_timestamp(
                now - timedelta(days=plan["completed_days_ago"])
            )

        batch = Batch(
            recipe_id=recipe.id,
            label_code=plan["label_code"],
            batch_type="product",
            projected_yield=recipe.predicted_yield * plan["scale"],
            projected_yield_unit=recipe.predicted_yield_unit,
            scale=plan["scale"],
            status=plan["status"],
            notes=plan.get("notes"),
            started_at=started_at,
            completed_at=completed_at if plan["status"] == "completed" else None,
            final_quantity=plan.get("final_quantity"),
            remaining_quantity=plan.get("remaining_quantity"),
            output_unit="unit",
            sku_id=product_sku.id,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(batch)
        db.session.flush()

        if plan["status"] == "completed":
            completed_batch_count += 1
        else:
            in_progress_batch_count += 1

        # Only completed batches drive inventory movements
        if plan["status"] == "completed":
            # Honey consumption
            honey_assoc = ingredient_map.get(honey_item.id)
            if honey_assoc:
                honey_required = convert_units(
                    honey_assoc.quantity * plan["scale"],
                    honey_assoc.unit,
                    honey_item.unit,
                    honey_item,
                )
                process_adjustment(
                    context=f"Honey usage {plan['label_code']}",
                    item_id=honey_item.id,
                    change_type="batch",
                    quantity=honey_required,
                    unit=honey_item.unit,
                    notes=f"Used in {plan['label_code']}",
                    created_by=admin_user.id,
                    batch_id=batch.id,
                    defer_commit=True,
                )

                # Create BatchIngredient record
                batch_ingredient = BatchIngredient(
                    batch_id=batch.id,
                    inventory_item_id=honey_item.id,
                    quantity_used=honey_required,
                    unit=honey_item.unit,
                    cost_per_unit=honey_item.cost_per_unit,
                    organization_id=organization_id,
                )
                db.session.add(batch_ingredient)

            # Milk consumption
            milk_assoc = ingredient_map.get(milk_item.id)
            if milk_assoc:
                milk_required = convert_units(
                    milk_assoc.quantity * plan["scale"],
                    milk_assoc.unit,
                    milk_item.unit,
                    milk_item,
                )
                process_adjustment(
                    context=f"Milk usage {plan['label_code']}",
                    item_id=milk_item.id,
                    change_type="batch",
                    quantity=milk_required,
                    unit=milk_item.unit,
                    notes=f"Used in {plan['label_code']}",
                    created_by=admin_user.id,
                    batch_id=batch.id,
                    defer_commit=True,
                )

                # Create BatchIngredient record
                batch_ingredient = BatchIngredient(
                    batch_id=batch.id,
                    inventory_item_id=milk_item.id,
                    quantity_used=milk_required,
                    unit=milk_item.unit,
                    cost_per_unit=milk_item.cost_per_unit,
                    organization_id=organization_id,
                )
                db.session.add(batch_ingredient)

            # Container consumption matches final output
            container_required = plan.get("final_quantity", 0) or 0
            if container_required:
                process_adjustment(
                    context=f"Container usage {plan['label_code']}",
                    item_id=container_item.id,
                    change_type="batch",
                    quantity=float(container_required),
                    unit=container_item.unit,
                    notes=f"Filled for {plan['label_code']}",
                    created_by=admin_user.id,
                    batch_id=batch.id,
                    defer_commit=True,
                )

                # Create BatchContainer record
                batch_container = BatchContainer(
                    batch_id=batch.id,
                    container_id=container_item.id,
                    container_quantity=int(container_required),
                    quantity_used=int(container_required),
                    fill_quantity=4.0,  # 4 fl oz per container
                    fill_unit="floz",
                    cost_each=container_item.cost_per_unit,
                )
                db.session.add(batch_container)

            # Finished goods lot
            if plan.get("final_quantity"):
                process_adjustment(
                    context=f"Finished goods {plan['label_code']}",
                    item_id=product_item.id,
                    change_type="finished_batch",
                    quantity=float(plan["final_quantity"]),
                    unit=product_item.unit,
                    notes=f"Finished goods from {plan['label_code']}",
                    cost_override=plan.get("unit_cost"),
                    created_by=admin_user.id,
                    batch_id=batch.id,
                    defer_commit=True,
                )
                db.session.flush()
                finished_lot = (
                    InventoryLot.query.filter_by(
                        inventory_item_id=product_item.id,
                        batch_id=batch.id,
                        source_type="finished_batch",
                    )
                    .order_by(InventoryLot.id.desc())
                    .first()
                )
                if finished_lot:
                    current_stamp = completed_at or normalize_timestamp(now)
                    expiration = (
                        current_stamp
                        + timedelta(days=product_item.shelf_life_days or 0)
                        if current_stamp
                        else None
                    )
                    update_lot_dates(
                        finished_lot,
                        current_stamp,
                        expiration_at=expiration,
                        source_notes=f"Finished goods from {plan['label_code']}",
                    )
                    total_lots_created += 1

            db.session.commit()

            update_history_timestamp(
                honey_item.id, "batch", completed_at, batch_id=batch.id
            )
            update_history_timestamp(
                milk_item.id, "batch", completed_at, batch_id=batch.id
            )
            update_history_timestamp(
                container_item.id, "batch", completed_at, batch_id=batch.id
            )
            update_history_timestamp(
                product_item.id, "finished_batch", completed_at, batch_id=batch.id
            )
            db.session.commit()

        batches_by_label[plan["label_code"]] = batch

    # ------------------------------------------------------------------
    # Sales history
    # ------------------------------------------------------------------
    sales_plan = [
        {
            "batch_label": "MH-240901",
            "quantity": 40,
            "days_ago": 31,
            "customer": "Saturday Farmers Market",
            "order_id": "FM-2409-22",
            "sale_price": 14.0,
        },
        {
            "batch_label": "MH-240915",
            "quantity": 50,
            "days_ago": 18,
            "customer": "Co-op Grocer",
            "order_id": "COOP-2410",
            "sale_price": 13.5,
        },
        {
            "batch_label": "MH-241001",
            "quantity": 50,
            "days_ago": 2,
            "customer": "Cafe Collective",
            "order_id": "CAFE-2411",
            "sale_price": 14.5,
        },
    ]

    # Sort sales by days_ago (oldest first) for chronological processing
    sorted_sales_plan = sorted(sales_plan, key=lambda x: x["days_ago"], reverse=True)

    for sale in sorted_sales_plan:
        sale_timestamp = normalize_timestamp(now - timedelta(days=sale["days_ago"]))
        notes = f"Sale {sale['order_id']} - {sale['customer']}"
        process_adjustment(
            context=f"Sale {sale['order_id']}",
            item_id=product_item.id,
            change_type="sale",
            quantity=float(sale["quantity"]),
            unit=product_item.unit,
            notes=notes,
            created_by=admin_user.id,
            customer=sale.get("customer"),
            sale_price=sale.get("sale_price"),
            order_id=sale.get("order_id"),
            batch_id=batches_by_label[sale["batch_label"]].id,
            defer_commit=True,
        )
        db.session.commit()
        update_history_timestamp(
            product_item.id,
            "sale",
            sale_timestamp,
            notes_contains=sale["order_id"],
            batch_id=batches_by_label[sale["batch_label"]].id,
        )
        db.session.commit()

    # ------------------------------------------------------------------
    # Active reservation using system adjustment
    # ------------------------------------------------------------------
    reservation_order_id = "ORDER-1098"
    Reservation.query.filter_by(
        order_id=reservation_order_id, organization_id=organization_id
    ).delete(synchronize_session=False)
    db.session.commit()

    reservation_timestamp = normalize_timestamp(now - timedelta(days=1))
    reservation_quantity = 2
    reservation_notes = f"Reservation {reservation_order_id} - Cafe Collective"

    process_adjustment(
        context="Reservation hold",
        item_id=product_item.id,
        change_type="reserved",
        quantity=float(reservation_quantity),
        unit=product_item.unit,
        notes=reservation_notes,
        created_by=admin_user.id,
        customer="Cafe Collective",
        sale_price=14.5,
        order_id=reservation_order_id,
        defer_commit=True,
    )
    db.session.commit()
    update_history_timestamp(
        product_item.id,
        "reserved",
        reservation_timestamp,
        notes_contains=reservation_order_id,
    )
    db.session.commit()

    reservation = Reservation(
        order_id=reservation_order_id,
        reservation_id="RES-1098",
        product_item_id=product_item.id,
        reserved_item_id=product_item.id,
        quantity=reservation_quantity,
        unit=product_item.unit,
        unit_cost=product_item.cost_per_unit,
        sale_price=14.5,
        customer="Cafe Collective",
        status="active",
        source="manual",
        created_at=reservation_timestamp,
        expires_at=normalize_timestamp(now + timedelta(days=5)),
        notes="Reserve inventory for Thursday pickup after cupping event.",
        created_by=admin_user.id,
        organization_id=organization_id,
    )
    db.session.add(reservation)
    db.session.commit()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    finished_on_hand = product_item.quantity or 0.0
    print("\n=== Living Account Summary ===")
    print(f"✅ Inventory Items Managed: {len(inventory_items)}")
    print(f"✅ Inventory Lots Created: {total_lots_created}")
    print(
        f"✅ Recipe Ready: {recipe.name} (yield {recipe.predicted_yield} {recipe.predicted_yield_unit})"
    )
    print(f"✅ Batches Completed: {completed_batch_count}")
    print(f"✅ Batches In Progress: {in_progress_batch_count}")
    print(f"✅ Finished Goods On Hand: {finished_on_hand} {product_item.unit}")
    print("✅ Active Reservations: 1")
    print("🧪 Dataset reflects a month of live operations with full history logs.")
