
#!/usr/bin/env python3
"""
Startup Recipe Loader - Load recipes from JSON export file
"""
import json
import os
from app import app, db
from app.models import Recipe, RecipeIngredient, InventoryItem
from flask import current_app

def load_recipes_from_json(json_file_path=None):
    """Load recipes from JSON export file and create recipe entries with ingredients"""
    
    if json_file_path is None:
        json_file_path = "attached_assets/recipes_export_20250430_235506 (1) (1).json"
    
    if not os.path.exists(json_file_path):
        print(f"❌ File not found: {json_file_path}")
        return False
    
    try:
        with open(json_file_path, 'r') as f:
            recipes_data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading JSON file: {e}")
        return False
    
    print(f"📖 Loading {len(recipes_data)} recipes...")
    
    recipes_created = 0
    recipes_skipped = 0
    ingredients_created = 0
    ingredient_errors = 0
    
    for recipe_data in recipes_data:
        try:
            # Check if recipe already exists
            existing_recipe = Recipe.query.filter_by(name=recipe_data['name']).first()
            
            if existing_recipe:
                print(f"⚠️  Recipe '{recipe_data['name']}' already exists, skipping...")
                recipes_skipped += 1
                continue
            
            # Create new recipe
            new_recipe = Recipe(
                name=recipe_data['name'],
                instructions=recipe_data.get('instructions', ''),
                label_prefix=recipe_data.get('label_prefix', ''),
                predicted_yield=recipe_data.get('predicted_yield', 0.0),
                predicted_yield_unit=recipe_data.get('predicted_yield_unit', 'count'),
                requires_containers=recipe_data.get('requires_containers', False),
                allowed_containers=recipe_data.get('allowed_containers', [])
            )
            
            db.session.add(new_recipe)
            db.session.flush()  # Get recipe ID
            
            # Add ingredients
            recipe_ingredients_count = 0
            for ingredient_data in recipe_data.get('ingredients', []):
                try:
                    # Find inventory item by name
                    inventory_item = InventoryItem.query.filter_by(
                        name=ingredient_data['inventory_item_name']
                    ).first()
                    
                    if not inventory_item:
                        print(f"⚠️  Ingredient '{ingredient_data['inventory_item_name']}' not found in inventory, skipping...")
                        ingredient_errors += 1
                        continue
                    
                    # Create recipe ingredient
                    recipe_ingredient = RecipeIngredient(
                        recipe_id=new_recipe.id,
                        inventory_item_id=inventory_item.id,
                        amount=ingredient_data['amount'],
                        unit=ingredient_data['unit']
                    )
                    
                    db.session.add(recipe_ingredient)
                    recipe_ingredients_count += 1
                    ingredients_created += 1
                    
                except Exception as e:
                    print(f"⚠️  Error adding ingredient '{ingredient_data.get('inventory_item_name', 'unknown')}': {e}")
                    ingredient_errors += 1
                    continue
            
            db.session.commit()
            print(f"✅ Created '{recipe_data['name']}' with {recipe_ingredients_count} ingredients")
            recipes_created += 1
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error creating recipe '{recipe_data.get('name', 'unknown')}': {e}")
            recipes_skipped += 1
            continue
    
    print(f"\n🎉 Startup recipe load complete!")
    print(f"   Recipes created: {recipes_created}")
    print(f"   Recipes skipped: {recipes_skipped}")
    print(f"   Ingredients created: {ingredients_created}")
    print(f"   Ingredient errors: {ingredient_errors}")
    
    return True

def validate_container_references():
    """Validate that allowed_containers reference existing container IDs"""
    print("\n🔍 Validating container references...")
    
    recipes_with_containers = Recipe.query.filter(Recipe.allowed_containers.isnot(None)).all()
    validation_issues = 0
    
    for recipe in recipes_with_containers:
        if recipe.allowed_containers:
            for container_id in recipe.allowed_containers:
                container = InventoryItem.query.filter_by(
                    id=container_id, 
                    type='container'
                ).first()
                
                if not container:
                    print(f"⚠️  Recipe '{recipe.name}' references non-existent container ID: {container_id}")
                    validation_issues += 1
    
    if validation_issues == 0:
        print("✅ All container references are valid")
    else:
        print(f"⚠️  Found {validation_issues} container reference issues")
    
    return validation_issues == 0

def run_startup_recipe_loader():
    """Main function to run the complete startup recipe load process"""
    print("🚀 Starting recipe loader...")
    
    success = load_recipes_from_json()
    
    if success:
        validate_container_references()
        print("\n✅ Startup recipe loader completed successfully!")
    else:
        print("\n❌ Startup recipe loader failed!")
    
    return success

if __name__ == '__main__':
    with app.app_context():
        run_startup_recipe_loader()
