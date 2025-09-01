from datetime import datetime, timedelta
from flask import current_app
from flask_login import current_user
from ..models import (
    InventoryItem, IngredientCategory, Unit, Recipe, RecipeIngredient,
    InventoryLot, Organization, User
)
from ..extensions import db
from ..utils.timezone_utils import TimezoneUtils


def seed_test_data(organization_id=None):
    """
    Seed comprehensive test data including:
    - Various inventory items with different units
    - Multiple lots (some expired, some fresh, some with no history)
    - Test recipes with unit conversions
    - Container items
    """

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

    print("=== Seeding Test Data ===")

    # Get categories
    liquid_cat = IngredientCategory.query.filter_by(name='Liquid', organization_id=organization_id).first()
    solid_cat = IngredientCategory.query.filter_by(name='Solid', organization_id=organization_id).first()
    oil_cat = IngredientCategory.query.filter_by(name='Oil', organization_id=organization_id).first()
    dairy_cat = IngredientCategory.query.filter_by(name='Dairy', organization_id=organization_id).first()
    wax_cat = IngredientCategory.query.filter_by(name='Wax', organization_id=organization_id).first()
    container_cat = IngredientCategory.query.filter_by(name='Container', organization_id=organization_id).first()

    if not liquid_cat:
        print("❌ Categories not found! Run category seeder first.")
        return

    # Get units
    units = {
        'count': Unit.query.filter_by(name='count').first(),
        'lb': Unit.query.filter_by(name='lb').first(),
        'kg': Unit.query.filter_by(name='kg').first(),
        'gallon': Unit.query.filter_by(name='gallon').first(),
        'liter': Unit.query.filter_by(name='liter').first(),
        'floz': Unit.query.filter_by(name='floz').first(),
        'ml': Unit.query.filter_by(name='ml').first(),
        'oz': Unit.query.filter_by(name='oz').first(),
        'gram': Unit.query.filter_by(name='gram').first(),
        'unit': Unit.query.filter_by(name='unit').first(),
    }

    # Test inventory items with various units for conversion testing
    test_items = [
        # Fruits (count units)
        {
            'name': 'Apples',
            'type': 'ingredient',
            'unit': 'count',
            'cost_per_unit': 0.75,
            'category_id': solid_cat.id,
            'is_perishable': True,
            'shelf_life_days': 7,
            'lots': [
                {'quantity': 50, 'unit_cost': 0.75, 'days_ago': 10, 'expired': True},  # Expired lot
                {'quantity': 100, 'unit_cost': 0.80, 'days_ago': 2, 'expired': False},  # Fresh lot
            ]
        },
        {
            'name': 'Bananas',
            'type': 'ingredient',
            'unit': 'count',
            'cost_per_unit': 0.50,
            'category_id': solid_cat.id,
            'is_perishable': True,
            'shelf_life_days': 5,
            'lots': [
                {'quantity': 24, 'unit_cost': 0.50, 'days_ago': 6, 'expired': True},  # Expired lot
                {'quantity': 36, 'unit_cost': 0.45, 'days_ago': 1, 'expired': False},  # Fresh lot
            ]
        },

        # Meat (weight units)
        {
            'name': 'Ground Beef',
            'type': 'ingredient',
            'unit': 'lb',
            'cost_per_unit': 8.99,
            'category_id': solid_cat.id,
            'is_perishable': True,
            'shelf_life_days': 3,
            'lots': [
                {'quantity': 5.0, 'unit_cost': 8.99, 'days_ago': 1, 'expired': False},
            ]
        },

        # Dairy (volume converted to weight)
        {
            'name': 'Whole Milk',
            'type': 'ingredient',
            'unit': 'gallon',
            'cost_per_unit': 4.50,
            'category_id': dairy_cat.id,
            'is_perishable': True,
            'shelf_life_days': 7,
            'lots': [
                {'quantity': 3.0, 'unit_cost': 4.50, 'days_ago': 2, 'expired': False},
                {'quantity': 2.0, 'unit_cost': 4.25, 'days_ago': 5, 'expired': False},
            ]
        },

        # Liquids for volume conversions
        {
            'name': 'Apple Cider Vinegar',
            'type': 'ingredient',
            'unit': 'liter',
            'cost_per_unit': 3.25,
            'category_id': liquid_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': [
                {'quantity': 2.0, 'unit_cost': 3.25, 'days_ago': 10, 'expired': False},
            ]
        },

        # Oil stored in volume
        {
            'name': 'Olive Oil',
            'type': 'ingredient',
            'unit': 'ml',
            'cost_per_unit': 0.02,
            'category_id': oil_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': [
                {'quantity': 1000.0, 'unit_cost': 0.02, 'days_ago': 15, 'expired': False},
            ]
        },

        # Wax (weight)
        {
            'name': 'Beeswax',
            'type': 'ingredient',
            'unit': 'oz',
            'cost_per_unit': 1.25,
            'category_id': wax_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': [
                {'quantity': 32.0, 'unit_cost': 1.25, 'days_ago': 30, 'expired': False},
            ]
        },

        # Sugar for weight conversions (kg to grams)
        {
            'name': 'Granulated Sugar',
            'type': 'ingredient',
            'unit': 'kg',
            'cost_per_unit': 3.50,
            'category_id': solid_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': [
                {'quantity': 5.0, 'unit_cost': 3.50, 'days_ago': 20, 'expired': False},
            ]
        },

        # Item with no lots/history for modal testing
        {
            'name': 'Vanilla Extract',
            'type': 'ingredient',
            'unit': 'floz',
            'cost_per_unit': 2.00,
            'category_id': liquid_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': []  # No lots - for testing initial entry
        },

        {
            'name': 'Sea Salt',
            'type': 'ingredient',
            'unit': 'gram',
            'cost_per_unit': 0.01,
            'category_id': solid_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': []  # No lots - for testing initial entry
        },

        # Containers
        {
            'name': 'Glass 4oz Jars',
            'type': 'container',
            'unit': 'unit',
            'cost_per_unit': 1.25,
            'category_id': container_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': [
                {'quantity': 50, 'unit_cost': 1.25, 'days_ago': 14, 'expired': False},
            ]
        },

        {
            'name': 'Glass 10oz Jars',
            'type': 'container',
            'unit': 'unit',
            'cost_per_unit': 1.75,
            'category_id': container_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': [
                {'quantity': 30, 'unit_cost': 1.75, 'days_ago': 14, 'expired': False},
            ]
        },

        {
            'name': 'Paper Plates (5-pack)',
            'type': 'container',
            'unit': 'unit',
            'cost_per_unit': 3.99,
            'category_id': container_cat.id,
            'is_perishable': False,
            'shelf_life_days': None,
            'lots': [
                {'quantity': 10, 'unit_cost': 3.99, 'days_ago': 7, 'expired': False},
            ]
        },
    ]

    print(f"Creating {len(test_items)} test inventory items...")

    created_items = {}
    total_lots = 0

    for item_data in test_items:
        # Create inventory item
        lots_data = item_data.pop('lots')

        # Check if item already exists
        existing_item = InventoryItem.query.filter_by(
            name=item_data['name'],
            organization_id=organization_id
        ).first()

        if existing_item:
            print(f"   ⚠️  Item {item_data['name']} already exists, skipping...")
            created_items[item_data['name']] = existing_item
            continue

        # Add organization_id and unit (keep as string, not unit_id)
        item_data['organization_id'] = organization_id
        unit_name = item_data['unit']
        # Keep unit as string since InventoryItem expects unit field, not unit_id

        # Set default quantity to 0 (will be updated by lots)
        item_data['quantity'] = 0.0

        # Add storage fields - set reasonable defaults based on item type
        item_data['capacity'] = 1.0  # Default storage capacity
        item_data['capacity_unit'] = item_data['unit']  # Use same unit as item unit

        inventory_item = InventoryItem(**item_data)
        db.session.add(inventory_item)
        db.session.flush()  # Get the ID

        created_items[inventory_item.name] = inventory_item

        # Create lots for this item
        total_quantity = 0.0
        for lot_data in lots_data:
            # Calculate expiration date
            received_date = TimezoneUtils.utc_now() - timedelta(days=lot_data['days_ago'])
            expiration_date = None

            if inventory_item.is_perishable and inventory_item.shelf_life_days:
                if lot_data.get('expired', False):
                    # Force expiration by setting shelf life to 1 day and received date further back
                    expiration_date = received_date + timedelta(days=1)
                else:
                    expiration_date = received_date + timedelta(days=inventory_item.shelf_life_days)

            lot = InventoryLot(
                inventory_item_id=inventory_item.id,
                remaining_quantity=lot_data['quantity'],
                original_quantity=lot_data['quantity'],
                unit=inventory_item.unit,  # Use unit string directly
                unit_cost=lot_data['unit_cost'],
                received_date=received_date,
                expiration_date=expiration_date,
                source_type='restock',
                source_notes='Test data seeder',
                created_by=admin_user.id,
                organization_id=organization_id,
                fifo_code=f"TEST-{inventory_item.id}-{len(lots_data)}-{lot_data['days_ago']}"
            )
            db.session.add(lot)
            db.session.flush()  # Get lot ID

            # Create history entry for this lot creation
            from app.models.unified_inventory_history import UnifiedInventoryHistory
            from datetime import datetime

            history_entry = UnifiedInventoryHistory(
                inventory_item_id=inventory_item.id,
                affected_lot_id=lot.id,
                action_type='lot_created',
                quantity_change=lot_data['quantity'],
                quantity_after=lot_data['quantity'],
                unit=inventory_item.unit,
                notes=f"Test data lot creation - {lot.batch_id}",
                created_at=datetime.utcnow(),
                organization_id=organization_id
            )
            db.session.add(history_entry)
            total_quantity += lot_data['quantity']
            total_lots += 1

        # Update item quantity
        inventory_item.quantity = total_quantity

        print(f"   ✅ Created {inventory_item.name} with {len(lots_data)} lots")

    # Commit all inventory items and lots
    try:
        db.session.commit()
        print(f"✅ Created {len(created_items)} inventory items with {total_lots} lots")
    except Exception as e:
        print(f"❌ Error creating inventory items: {e}")
        db.session.rollback()
        return

    # Create test recipes
    print("\nCreating test recipes...")

    recipes_data = [
        {
            'name': 'Simple Applesauce',
            'instructions': 'Blend apples until smooth. Pour into glass containers.',
            'predicted_yield': 4.0,
            'predicted_yield_unit': 'floz',
            'ingredients': [
                {'name': 'Apples', 'quantity': 3, 'unit': 'count'},  # 3 apples -> 4 fl oz
                {'name': 'Granulated Sugar', 'quantity': 50, 'unit': 'gram'},  # kg to gram conversion
            ],
            'containers': ['Glass 4oz Jars']
        },
        {
            'name': 'Milk and Honey Mixture',
            'instructions': 'Recipe testing gallon to liter and volume conversions',
            'predicted_yield': 500.0,
            'predicted_yield_unit': 'ml',
            'ingredients': [
                {'name': 'Whole Milk', 'quantity': 0.25, 'unit': 'gallon'},  # Gallon to liter conversion
                {'name': 'Vanilla Extract', 'quantity': 1, 'unit': 'floz'},  # Volume mixing
            ],
            'containers': ['Glass 10oz Jars']
        },
        {
            'name': 'Complex Conversion Test',
            'instructions': 'Recipe testing multiple unit conversions simultaneously',
            'predicted_yield': 1.0,
            'predicted_yield_unit': 'liter',
            'ingredients': [
                {'name': 'Olive Oil', 'quantity': 250, 'unit': 'ml'},  # ml to liter
                {'name': 'Apple Cider Vinegar', 'quantity': 0.5, 'unit': 'liter'},  # liter to ml
                {'name': 'Beeswax', 'quantity': 2, 'unit': 'oz'},  # oz to gram conversion
                {'name': 'Sea Salt', 'quantity': 5, 'unit': 'gram'},  # direct gram
            ],
            'containers': ['Glass 10oz Jars', 'Glass 4oz Jars']
        },
        {
            'name': 'Fruit Salad',
            'instructions': 'Multi-fruit recipe with perishable ingredients',
            'predicted_yield': 2.0,
            'predicted_yield_unit': 'lb',
            'ingredients': [
                {'name': 'Apples', 'quantity': 5, 'unit': 'count'},
                {'name': 'Bananas', 'quantity': 3, 'unit': 'count'},
                {'name': 'Granulated Sugar', 'quantity': 100, 'unit': 'gram'},
            ],
            'containers': ['Paper Plates (5-pack)']
        }
    ]

    created_recipes = 0
    for recipe_data in recipes_data:
        # Check if recipe exists
        existing_recipe = Recipe.query.filter_by(
            name=recipe_data['name'],
            organization_id=organization_id
        ).first()

        if existing_recipe:
            print(f"   ⚠️  Recipe {recipe_data['name']} already exists, skipping...")
            continue

        # Create recipe
        recipe = Recipe(
            name=recipe_data['name'],
            instructions=recipe_data['instructions'],
            predicted_yield=recipe_data['predicted_yield'],
            predicted_yield_unit=recipe_data['predicted_yield_unit'],
            organization_id=organization_id  # Add organization_id
        )
        db.session.add(recipe)
        db.session.flush()  # Get the ID

        # Add ingredients
        for ingredient_data in recipe_data['ingredients']:
            inventory_item = created_items.get(ingredient_data['name'])
            if not inventory_item:
                print(f"   ⚠️  Ingredient {ingredient_data['name']} not found for recipe {recipe_data['name']}")
                continue

            unit = units.get(ingredient_data['unit'])
            if not unit:
                print(f"   ⚠️  Unit {ingredient_data['unit']} not found")
                continue

            recipe_ingredient = RecipeIngredient(
                recipe_id=recipe.id,
                inventory_item_id=inventory_item.id,
                quantity=ingredient_data['quantity'],
                unit=ingredient_data['unit'],  # Use unit string instead of unit_id
                organization_id=organization_id
            )
            db.session.add(recipe_ingredient)

        # Add allowed containers
        for container_name in recipe_data['containers']:
            container_item = created_items.get(container_name)
            if container_item:
                recipe.allowed_containers.append(container_item)

        print(f"   ✅ Created recipe: {recipe.name}")
        created_recipes += 1

    try:
        db.session.commit()
        print(f"✅ Created {created_recipes} test recipes")
    except Exception as e:
        print(f"❌ Error creating recipes: {e}")
        db.session.rollback()
        return

    # Summary
    print("\n=== Test Data Summary ===")
    print(f"✅ Inventory Items: {len(created_items)}")
    print(f"✅ Inventory Lots: {total_lots}")
    print(f"✅ Recipes: {created_recipes}")
    print("\n📋 Test Scenarios Available:")
    print("   • Unit conversions (count→volume, weight→volume, volume→volume)")
    print("   • Expired lots (apples, bananas)")
    print("   • Fresh lots with various ages")
    print("   • Items with no history (vanilla extract, sea salt)")
    print("   • Perishable and non-perishable items")
    print("   • Container management")
    print("   • Complex multi-ingredient recipes")
    print("\n🧪 Ready for comprehensive system testing!")