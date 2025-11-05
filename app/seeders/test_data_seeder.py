from datetime import timedelta
from typing import Dict, Optional

from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils
from ..models import (
    InventoryItem,
    IngredientCategory,
    InventoryLot,
    Organization,
    Product,
    ProductCategory,
    ProductSKU,
    ProductSKUHistory,
    ProductVariant,
    Recipe,
    RecipeIngredient,
    Reservation,
    Unit,
    User,
    Batch,
    BatchIngredient,
    BatchContainer,
    UnifiedInventoryHistory,
    GlobalItem,
)


HONEY_CUP_TO_LB = 0.741  # Approximate density conversion for honey
MILK_CL_TO_GALLON = 0.1 / 3.78541  # 10 cl = 0.1 L converted to gallons


def seed_test_data(organization_id: Optional[int] = None):
    """Seed living-account data geared toward milk & honey production."""

    if organization_id is None:
        org = Organization.query.first()
        if not org:
            print("❌ No organization found! Run user seeder first.")
            return
        organization_id = org.id

    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        print("❌ Admin user not found! Run user seeder first.")
        return

    now = TimezoneUtils.utc_now()
    print("=== Seeding Living Account Test Data ===")

    def ensure_unit(name: str, symbol: str, unit_type: str, base_unit: str, conversion_factor: float):
        unit = Unit.query.filter_by(name=name, organization_id=None).first()
        if not unit:
            unit = Unit(
                name=name,
                symbol=symbol,
                unit_type=unit_type,
                base_unit=base_unit,
                conversion_factor=conversion_factor,
                is_custom=False,
                is_mapped=True,
                organization_id=None,
                created_by=admin_user.id,
            )
            db.session.add(unit)
            db.session.flush()
            print(f"   ➕ Added unit '{name}'")
        return unit

    def get_or_create_category(name: str) -> IngredientCategory:
        category = IngredientCategory.query.filter_by(name=name, organization_id=organization_id).first()
        if not category:
            category = IngredientCategory(name=name, organization_id=organization_id)
            db.session.add(category)
            db.session.flush()
            print(f"   ➕ Created ingredient category '{name}'")
        return category

    def ensure_global_item(name: str, item_type: str, defaults: Dict) -> GlobalItem:
        global_item = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
        if not global_item:
            global_item = GlobalItem(name=name, item_type=item_type, **defaults)
            db.session.add(global_item)
            db.session.flush()
            print(f"   🌐 Registered global item '{name}' ({item_type})")
        return global_item

    def log_history(
        item: InventoryItem,
        change_type: str,
        quantity_change: float,
        unit: str,
        timestamp,
        notes: str = "",
        batch: Optional[Batch] = None,
        lot: Optional[InventoryLot] = None,
        extra: Optional[Dict] = None,
    ) -> UnifiedInventoryHistory:
        history = UnifiedInventoryHistory(
            inventory_item_id=item.id,
            change_type=change_type,
            quantity_change=quantity_change,
            unit=unit,
            timestamp=timestamp,
            organization_id=organization_id,
            created_by=admin_user.id,
            notes=notes,
        )
        if batch:
            history.batch_id = batch.id
        if lot:
            history.affected_lot_id = lot.id
            history.fifo_code = lot.fifo_code
        if extra:
            for key, value in extra.items():
                setattr(history, key, value)
        db.session.add(history)
        return history

    # Ensure required units and categories exist
    ensure_unit('cup', 'cup', 'volume', 'ml', 236.588)
    ensure_unit('cl', 'cL', 'volume', 'ml', 10.0)

    categories = {
        name: get_or_create_category(name)
        for name in ['Dairy', 'Syrups', 'Container', 'Other']
    }

    beverage_category = ProductCategory.query.filter_by(name='Beverages').first()
    if not beverage_category:
        beverage_category = ProductCategory(
            name='Beverages',
            is_typically_portioned=False,
            sku_name_template='{variant} {product} ({container})',
            skin_enabled=False,
        )
        db.session.add(beverage_category)
        db.session.flush()
        print("   ➕ Created product category 'Beverages'")

    # Stage 1: Seed inventory for living operations
    print("\n→ Building ingredient and container inventory...")

    living_inventory_plan = [
        {
            'key': 'Whole Milk',
            'name': 'Whole Milk',
            'type': 'ingredient',
            'unit': 'gallon',
            'cost_per_unit': 4.95,
            'category': categories['Dairy'],
            'density': 1.03,
            'is_perishable': True,
            'shelf_life_days': 7,
            'global_item': {
                'name': 'Whole Milk',
                'item_type': 'ingredient',
                'density': 1.03,
                'default_unit': 'gallon',
                'ingredient_category_id': categories['Dairy'].id,
                'recommended_shelf_life_days': 7,
            },
            'lots': [
                {'code': 'MILK-LOT-A', 'quantity': 2.5, 'remaining_quantity': 0.0, 'unit_cost': 4.75, 'days_ago': 32, 'expired': True, 'notes': 'Opening month delivery'},
                {'code': 'MILK-LOT-B', 'quantity': 3.0, 'remaining_quantity': 1.8, 'unit_cost': 4.95, 'days_ago': 12, 'notes': 'Weekly restock from local dairy'},
                {'code': 'MILK-LOT-C', 'quantity': 3.0, 'remaining_quantity': 2.74, 'unit_cost': 5.05, 'days_ago': 4, 'notes': 'Fresh restock pending current batch'},
            ],
        },
        {
            'key': 'Wildflower Honey',
            'name': 'Wildflower Honey',
            'type': 'ingredient',
            'unit': 'lb',
            'cost_per_unit': 3.85,
            'category': categories['Syrups'],
            'density': 1.42,
            'is_perishable': True,
            'shelf_life_days': 540,
            'global_item': {
                'name': 'Honey',
                'item_type': 'ingredient',
                'density': 1.42,
                'default_unit': 'lb',
                'ingredient_category_id': categories['Syrups'].id,
                'recommended_shelf_life_days': 540,
            },
            'lots': [
                {'code': 'HONEY-LOT-A', 'quantity': 50.0, 'remaining_quantity': 0.0, 'unit_cost': 3.45, 'days_ago': 210, 'expired': True, 'notes': 'Legacy drum now empty'},
                {'code': 'HONEY-LOT-B', 'quantity': 55.0, 'remaining_quantity': 20.0, 'unit_cost': 3.75, 'days_ago': 45, 'notes': 'Summer harvest purchase'},
                {'code': 'HONEY-LOT-C', 'quantity': 55.0, 'remaining_quantity': 28.85, 'unit_cost': 3.95, 'days_ago': 8, 'notes': 'Recent cooperative delivery'},
            ],
        },
        {
            'key': '4 fl oz Boston Round Bottle',
            'name': '4 fl oz Boston Round Bottle',
            'type': 'container',
            'unit': 'unit',
            'cost_per_unit': 0.82,
            'category': categories['Container'],
            'capacity': 4.0,
            'capacity_unit': 'floz',
            'container_style': 'Boston Round',
            'container_material': 'Glass',
            'container_type': 'Bottle',
            'global_item': {
                'name': 'Boston Round Bottle 4 fl oz',
                'item_type': 'container',
                'capacity': 4.0,
                'capacity_unit': 'floz',
                'container_style': 'Boston Round',
                'container_material': 'Glass',
                'container_type': 'Bottle',
            },
            'lots': [
                {'code': 'BOSTON-LOT-A', 'quantity': 120, 'remaining_quantity': 75, 'unit_cost': 0.8, 'days_ago': 35, 'notes': 'Bulk glass pallet'},
                {'code': 'BOSTON-LOT-B', 'quantity': 80, 'remaining_quantity': 70, 'unit_cost': 0.84, 'days_ago': 7, 'notes': 'Top off order for autumn promotions'},
                {'code': 'BOSTON-LOT-C', 'quantity': 40, 'remaining_quantity': 0, 'unit_cost': 0.86, 'days_ago': 52, 'notes': 'Legacy lot fully consumed'},
            ],
        },
    ]

    inventory_items: Dict[str, InventoryItem] = {}
    total_lots_created = 0
    inventory_items_created = 0

    for item_data in living_inventory_plan:
        lots_data = item_data.pop('lots')
        global_item_meta = item_data.pop('global_item')

        existing_item = InventoryItem.query.filter_by(
            name=item_data['name'],
            organization_id=organization_id,
        ).first()

        if existing_item:
            inventory_item = existing_item
            inventory_item.unit = item_data['unit']
            inventory_item.cost_per_unit = item_data['cost_per_unit']
            inventory_item.category_id = item_data['category'].id if item_data.get('category') else None
            inventory_item.density = item_data.get('density')
            inventory_item.type = item_data['type']
            inventory_item.is_perishable = item_data.get('is_perishable', False)
            inventory_item.shelf_life_days = item_data.get('shelf_life_days')
            inventory_item.capacity = item_data.get('capacity')
            inventory_item.capacity_unit = item_data.get('capacity_unit')
            inventory_item.container_style = item_data.get('container_style')
            inventory_item.container_material = item_data.get('container_material')
            inventory_item.container_type = item_data.get('container_type')
            # Reset existing lots for a clean reseed
            for lot in list(inventory_item.lots):
                db.session.delete(lot)
            inventory_item.quantity = 0
            print(f"   ↻ Reset inventory item '{inventory_item.name}' to living configuration")
        else:
            inventory_item = InventoryItem(
                name=item_data['name'],
                unit=item_data['unit'],
                cost_per_unit=item_data['cost_per_unit'],
                category_id=item_data['category'].id if item_data.get('category') else None,
                density=item_data.get('density'),
                type=item_data['type'],
                is_perishable=item_data.get('is_perishable', False),
                shelf_life_days=item_data.get('shelf_life_days'),
                capacity=item_data.get('capacity'),
                capacity_unit=item_data.get('capacity_unit'),
                container_style=item_data.get('container_style'),
                container_material=item_data.get('container_material'),
                container_type=item_data.get('container_type'),
                quantity=0.0,
                organization_id=organization_id,
                created_by=admin_user.id,
            )
            db.session.add(inventory_item)
            db.session.flush()
            inventory_items_created += 1
            print(f"   ✅ Created inventory item '{inventory_item.name}'")

        global_item = ensure_global_item(global_item_meta['name'], global_item_meta['item_type'], {
            key: value for key, value in global_item_meta.items() if key not in {'name', 'item_type'}
        })
        inventory_item.global_item_id = global_item.id
        inventory_item.reference_item_name = global_item.name

        inventory_items[item_data['key']] = inventory_item

        # Create lots
        item_total_quantity = 0.0
        for idx, lot_data in enumerate(lots_data):
            received_date = now - timedelta(days=lot_data['days_ago'])
            expiration_date = None
            if inventory_item.is_perishable and inventory_item.shelf_life_days:
                if lot_data.get('expired'):
                    expiration_date = received_date + timedelta(days=1)
                else:
                    expiration_date = received_date + timedelta(days=inventory_item.shelf_life_days)

            lot = InventoryLot(
                inventory_item_id=inventory_item.id,
                remaining_quantity=lot_data.get('remaining_quantity', lot_data['quantity']),
                original_quantity=lot_data['quantity'],
                unit=inventory_item.unit,
                unit_cost=lot_data['unit_cost'],
                received_date=received_date,
                expiration_date=expiration_date,
                shelf_life_days=inventory_item.shelf_life_days,
                source_type='restock',
                source_notes=lot_data.get('notes', 'Restock'),
                created_by=admin_user.id,
                organization_id=organization_id,
                fifo_code=f"LIVING-{inventory_item.id}-{idx + 1}-{int(received_date.timestamp())}",
            )
            db.session.add(lot)
            db.session.flush()

            item_total_quantity += lot.remaining_quantity
            total_lots_created += 1

            log_history(
                item=inventory_item,
                change_type='lot_created',
                quantity_change=lot.original_quantity,
                unit=inventory_item.unit,
                timestamp=received_date,
                notes=f"Lot {lot_data.get('code', idx + 1)} received",
                lot=lot,
            )

        inventory_item.quantity = item_total_quantity

    # Stage 2: Recipe configuration
    print("\n→ Configuring milk & honey recipe...")

    container_item = inventory_items['4 fl oz Boston Round Bottle']
    recipe_name = 'Milk & Honey Elixir'
    recipe = Recipe.query.filter_by(name=recipe_name, organization_id=organization_id).first()

    if not recipe:
        recipe = Recipe(
            name=recipe_name,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(recipe)

    recipe.instructions = (
        "Warm milk to 120°F, dissolve honey, and blend until uniform. Cool and "
        "bottle immediately to maintain suspension."
    )
    recipe.predicted_yield = 4.0
    recipe.predicted_yield_unit = 'floz'
    recipe.is_portioned = False
    recipe.portioning_data = None
    recipe.allowed_containers = [container_item.id]
    recipe.category_id = beverage_category.id

    # Reset recipe ingredients for deterministic seeding
    for existing in list(recipe.recipe_ingredients):
        db.session.delete(existing)

    recipe_ingredients_data = [
        {'item_key': 'Wildflower Honey', 'quantity': 1.0, 'unit': 'cup', 'order': 0},
        {'item_key': 'Whole Milk', 'quantity': 10.0, 'unit': 'cl', 'order': 1},
    ]

    for ingredient in recipe_ingredients_data:
        inv_item = inventory_items[ingredient['item_key']]
        recipe_ingredient = RecipeIngredient(
            recipe=recipe,
            inventory_item_id=inv_item.id,
            quantity=ingredient['quantity'],
            unit=ingredient['unit'],
            order_position=ingredient['order'],
            organization_id=organization_id,
        )
        db.session.add(recipe_ingredient)

    print(f"   ✅ Recipe '{recipe_name}' refreshed with living ingredient data")

    # Stage 3: Finished goods inventory, product, and SKU
    print("\n→ Creating finished goods product & SKU...")

    product_item_key = 'Milk & Honey Elixir (Finished)'
    product_item = InventoryItem.query.filter_by(
        name=product_item_key,
        organization_id=organization_id,
    ).first()

    if product_item:
        for lot in list(product_item.lots):
            db.session.delete(lot)
        product_item.quantity = 0
        print("   ↻ Reset finished goods inventory")
    else:
        product_item = InventoryItem(
            name=product_item_key,
            unit='unit',
            cost_per_unit=7.5,
            category_id=categories['Other'].id,
            type='product',
            is_perishable=True,
            shelf_life_days=45,
            quantity=0.0,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(product_item)
        db.session.flush()
        inventory_items_created += 1
        print("   ✅ Created finished goods inventory item")

    inventory_items[product_item_key] = product_item

    product = Product.query.filter_by(name='Milk & Honey Elixir', organization_id=organization_id).first()
    if not product:
        product = Product(
            name='Milk & Honey Elixir',
            description='Gently warmed whole milk blended with raw wildflower honey.',
            category_id=beverage_category.id,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(product)
        db.session.flush()
        print("   ✅ Created product profile")

    variant = ProductVariant.query.filter_by(product_id=product.id, name='Original').first()
    if not variant:
        variant = ProductVariant(
            product_id=product.id,
            name='Original',
            description='Classic formulation',
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(variant)
        db.session.flush()
        print("   ✅ Added product variant")

    product_sku = ProductSKU.query.filter_by(inventory_item_id=product_item.id).first()
    if not product_sku:
        product_sku = ProductSKU(
            inventory_item_id=product_item.id,
            product_id=product.id,
            variant_id=variant.id,
            size_label='4 fl oz',
            sku='MH-ELIXIR-4OZ',
            sku_code='MH-ELIXIR-4OZ',
            sku_name='Milk & Honey Elixir 4 fl oz',
            unit='unit',
            retail_price=14.0,
            wholesale_price=9.5,
            low_stock_threshold=12,
            organization_id=organization_id,
            created_by=admin_user.id,
        )
        db.session.add(product_sku)
        db.session.flush()
        print("   ✅ Created product SKU")

    # Stage 4: Completed & in-progress batches
    print("\n→ Generating historical batches...")

    batch_plan = [
        {
            'label_code': 'MH-240901',
            'scale': 40,
            'status': 'completed',
            'started_days_ago': 34,
            'completed_days_ago': 33,
            'final_quantity': 40,
            'remaining_quantity': 0,
            'notes': 'Pilot production for wholesale tastings',
        },
        {
            'label_code': 'MH-240915',
            'scale': 50,
            'status': 'completed',
            'started_days_ago': 20,
            'completed_days_ago': 19,
            'final_quantity': 50,
            'remaining_quantity': 0,
            'notes': 'Market release run fulfilling co-op orders',
        },
        {
            'label_code': 'MH-241001',
            'scale': 60,
            'status': 'completed',
            'started_days_ago': 6,
            'completed_days_ago': 5,
            'final_quantity': 60,
            'remaining_quantity': 10,
            'notes': 'Bulk run ahead of holiday demand',
        },
        {
            'label_code': 'MH-Current',
            'scale': 25,
            'status': 'in_progress',
            'started_days_ago': 1,
            'completed_days_ago': None,
            'final_quantity': None,
            'remaining_quantity': None,
            'notes': 'Current batch staged and heating',
        },
    ]

    batches_by_label: Dict[str, Batch] = {}
    completed_batch_count = 0
    in_progress_batch_count = 0

    honey_item = inventory_items['Wildflower Honey']
    milk_item = inventory_items['Whole Milk']

    for plan in batch_plan:
        batch = Batch.query.filter_by(label_code=plan['label_code'], organization_id=organization_id).first()

        started_at = now - timedelta(days=plan['started_days_ago'])
        completed_at = None
        if plan['status'] == 'completed':
            completed_at = now - timedelta(days=plan['completed_days_ago'])

        if batch:
            for ingredient in list(batch.batch_ingredients):
                db.session.delete(ingredient)
            for container in list(batch.containers):
                db.session.delete(container)
            batch.scale = plan['scale']
            batch.status = plan['status']
            batch.projected_yield = plan['scale'] * 4.0
            batch.projected_yield_unit = 'floz'
            batch.batch_type = 'product'
            batch.label_code = plan['label_code']
            batch.recipe = recipe
            batch.started_at = started_at
            batch.completed_at = completed_at
            batch.final_quantity = plan['final_quantity']
            batch.remaining_quantity = plan['remaining_quantity']
            batch.notes = plan['notes']
            batch.sku_id = product_sku.id
            batch.output_unit = 'unit'
            batch.organization_id = organization_id
            print(f"   ↻ Updated batch {plan['label_code']}")
        else:
            batch = Batch(
                recipe_id=recipe.id,
                label_code=plan['label_code'],
                batch_type='product',
                projected_yield=plan['scale'] * 4.0,
                projected_yield_unit='floz',
                scale=plan['scale'],
                status=plan['status'],
                notes=plan['notes'],
                started_at=started_at,
                completed_at=completed_at,
                final_quantity=plan['final_quantity'],
                remaining_quantity=plan['remaining_quantity'],
                sku_id=product_sku.id,
                output_unit='unit',
                organization_id=organization_id,
                created_by=admin_user.id,
            )
            db.session.add(batch)
            print(f"   ✅ Recorded batch {plan['label_code']}")

        if plan['status'] == 'completed':
            completed_batch_count += 1
        else:
            in_progress_batch_count += 1

        honey_usage = 0.0 if plan['status'] != 'completed' else round(plan['scale'] * HONEY_CUP_TO_LB, 3)
        milk_usage = 0.0 if plan['status'] != 'completed' else round(plan['scale'] * MILK_CL_TO_GALLON, 3)

        honey_batch_ing = BatchIngredient(
            batch=batch,
            inventory_item_id=honey_item.id,
            quantity_used=honey_usage,
            unit='lb',
            cost_per_unit=honey_item.cost_per_unit,
            organization_id=organization_id,
        )
        db.session.add(honey_batch_ing)

        milk_batch_ing = BatchIngredient(
            batch=batch,
            inventory_item_id=milk_item.id,
            quantity_used=milk_usage,
            unit='gallon',
            cost_per_unit=milk_item.cost_per_unit,
            organization_id=organization_id,
        )
        db.session.add(milk_batch_ing)

        if plan['status'] == 'completed' and plan['final_quantity']:
            container_batch = BatchContainer(
                batch=batch,
                container_id=container_item.id,
                container_quantity=plan['final_quantity'],
                quantity_used=plan['final_quantity'],
                fill_quantity=4.0,
                fill_unit='floz',
                cost_each=container_item.cost_per_unit,
            )
            db.session.add(container_batch)

        batches_by_label[plan['label_code']] = batch

    # Stage 5: Product lots tied to batches
    print("\n→ Building finished goods lots...")

    product_lot_plan = [
        {'batch_label': 'MH-240901', 'quantity': 40, 'remaining_quantity': 0, 'unit_cost': 6.8},
        {'batch_label': 'MH-240915', 'quantity': 50, 'remaining_quantity': 0, 'unit_cost': 6.7},
        {'batch_label': 'MH-241001', 'quantity': 60, 'remaining_quantity': 10, 'unit_cost': 6.65},
    ]

    product_on_hand = 0.0

    for lot_idx, plan in enumerate(product_lot_plan):
        batch = batches_by_label[plan['batch_label']]
        completed_at = batch.completed_at or now
        lot = InventoryLot(
            inventory_item_id=product_item.id,
            remaining_quantity=plan['remaining_quantity'],
            original_quantity=plan['quantity'],
            unit='unit',
            unit_cost=plan['unit_cost'],
            received_date=completed_at,
            expiration_date=completed_at + timedelta(days=product_item.shelf_life_days or 0),
            shelf_life_days=product_item.shelf_life_days,
            source_type='finished_batch',
            source_notes=f'Finished goods from {batch.label_code}',
            batch_id=batch.id,
            created_by=admin_user.id,
            organization_id=organization_id,
            fifo_code=f"FIN-{product_item.id}-{lot_idx + 1}-{int(completed_at.timestamp())}",
        )
        db.session.add(lot)
        db.session.flush()

        product_on_hand += plan['remaining_quantity']
        total_lots_created += 1

        log_history(
            item=product_item,
            change_type='batch_completed',
            quantity_change=plan['quantity'],
            unit='unit',
            timestamp=completed_at,
            notes=f'Finished goods created via {batch.label_code}',
            batch=batch,
            lot=lot,
        )

    product_item.quantity = product_on_hand

    # Stage 6: Inventory usage & sales history
    print("\n→ Logging inventory movements...")

    for plan in batch_plan:
        if plan['status'] != 'completed':
            continue
        batch = batches_by_label[plan['label_code']]
        completed_at = batch.completed_at or now

        honey_usage = round(plan['scale'] * HONEY_CUP_TO_LB, 3)
        milk_usage = round(plan['scale'] * MILK_CL_TO_GALLON, 3)
        container_usage = plan['final_quantity'] or 0

        log_history(
            item=honey_item,
            change_type='batch_usage',
            quantity_change=-honey_usage,
            unit='lb',
            timestamp=completed_at,
            notes=f'Consumed for {batch.label_code}',
            batch=batch,
        )

        log_history(
            item=milk_item,
            change_type='batch_usage',
            quantity_change=-milk_usage,
            unit='gallon',
            timestamp=completed_at,
            notes=f'Consumed for {batch.label_code}',
            batch=batch,
        )

        if container_usage:
            log_history(
                item=container_item,
                change_type='batch_usage',
                quantity_change=-container_usage,
                unit='unit',
                timestamp=completed_at,
                notes=f'Containers filled for {batch.label_code}',
                batch=batch,
            )

    sales_plan = [
        {'batch_label': 'MH-240901', 'quantity': 40, 'days_ago': 31, 'customer': 'Saturday Farmers Market', 'order_id': 'FM-2409-22', 'sale_price': 14.0},
        {'batch_label': 'MH-240915', 'quantity': 50, 'days_ago': 18, 'customer': 'Co-op Grocer', 'order_id': 'COOP-2410', 'sale_price': 13.5},
        {'batch_label': 'MH-241001', 'quantity': 50, 'days_ago': 2, 'customer': 'Cafe Collective', 'order_id': 'CAFE-2411', 'sale_price': 14.5},
    ]

    running_finished_qty = 0.0

    # Production entries for SKU history
    for plan in product_lot_plan:
        batch = batches_by_label[plan['batch_label']]
        production_time = batch.completed_at or now
        running_finished_qty += plan['quantity']
        sku_history = ProductSKUHistory(
            inventory_item_id=product_item.id,
            change_type='production_completed',
            quantity_change=plan['quantity'],
            remaining_quantity=running_finished_qty,
            unit='unit',
            unit_cost=plan['unit_cost'],
            batch_id=batch.id,
            fifo_code=f"SKU-{batch.label_code}-PROD",
            timestamp=production_time,
            organization_id=organization_id,
            created_by=admin_user.id,
            notes=f'Finished goods received from {batch.label_code}',
        )
        db.session.add(sku_history)

    for sale in sales_plan:
        batch = batches_by_label[sale['batch_label']]
        sale_timestamp = now - timedelta(days=sale['days_ago'])
        running_finished_qty -= sale['quantity']

        log_history(
            item=product_item,
            change_type='sale',
            quantity_change=-sale['quantity'],
            unit='unit',
            timestamp=sale_timestamp,
            notes=f"Sold via {sale['customer']}",
            batch=batch,
            extra={
                'customer': sale['customer'],
                'order_id': sale['order_id'],
                'sale_price': sale['sale_price'],
            },
        )

        sku_sale = ProductSKUHistory(
            inventory_item_id=product_item.id,
            change_type='sale',
            quantity_change=-sale['quantity'],
            remaining_quantity=max(running_finished_qty, 0.0),
            unit='unit',
            sale_price=sale['sale_price'],
            customer=sale['customer'],
            order_id=sale['order_id'],
            batch_id=batch.id,
            fifo_code=f"SKU-{batch.label_code}-SALE",
            timestamp=sale_timestamp,
            organization_id=organization_id,
            created_by=admin_user.id,
            notes=f"Sale fulfilled for {sale['customer']}",
        )
        db.session.add(sku_sale)

    # Align finished goods quantity with remaining SKU balance
    product_item.quantity = max(running_finished_qty, 0.0)

    # Stage 7: Active reservation
    print("\n→ Creating active reservations...")

    reservation = Reservation(
        order_id='ORDER-1098',
        reservation_id='RES-1098',
        product_item_id=product_item.id,
        reserved_item_id=product_item.id,
        quantity=2,
        unit='unit',
        unit_cost=product_item.cost_per_unit,
        sale_price=14.5,
        customer='Cafe Collective',
        status='active',
        source='manual',
        created_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=5),
        notes='Reserve inventory for Thursday pickup after cupping event.',
        created_by=admin_user.id,
        organization_id=organization_id,
    )
    db.session.add(reservation)
    reservations_created = 1

    # Finalize
    try:
        db.session.commit()
        print("\n=== Living Account Summary ===")
        print(f"✅ Inventory Items Created/Updated: {inventory_items_created}")
        print(f"✅ Inventory Lots Created: {total_lots_created}")
        print(f"✅ Recipe Ready: {recipe.name} (yield {recipe.predicted_yield} {recipe.predicted_yield_unit})")
        print(f"✅ Batches Completed: {completed_batch_count}")
        print(f"✅ Batches In Progress: {in_progress_batch_count}")
        print(f"✅ Finished Goods On Hand: {product_item.quantity} {product_item.unit}")
        print(f"✅ Active Reservations: {reservations_created}")
        print("🧪 Dataset ready for full living-account workflows.")
    except Exception as exc:
        db.session.rollback()
        print(f"❌ Error seeding living data: {exc}")
        raise