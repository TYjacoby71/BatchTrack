
import json
from app import app, db
from models import Recipe, RecipeIngredient, InventoryItem

JSON_PATH = 'recipes_export_20250430_235506 (1).json'

def startup_recipe_service():
    """Import legacy recipes using proper creation workflows"""
    with app.app_context():
        try:
            with open(JSON_PATH, 'r') as f:
                recipe_data = json.load(f)
        except FileNotFoundError:
            print(f"❌ Recipe file {JSON_PATH} not found")
            return False

        created_count = 0
        skipped_count = 0
        
        print("🚀 Starting recipe import service...")

        for recipe_data_item in recipe_data:
            # Check if recipe already exists
            existing_recipe = Recipe.query.filter_by(name=recipe_data_item['name']).first()
            if existing_recipe:
                print(f"[SKIPPED] Recipe '{recipe_data_item['name']}' already exists")
                skipped_count += 1
                continue

            # Create new recipe
            recipe = Recipe(
                name=recipe_data_item['name'],
                instructions=recipe_data_item.get('instructions', ''),
                label_prefix=recipe_data_item.get('label_prefix', ''),
                predicted_yield=recipe_data_item.get('predicted_yield', 0.0),
                predicted_yield_unit=recipe_data_item.get('predicted_yield_unit', 'count'),
                requires_containers=recipe_data_item.get('requires_containers', False),
                allowed_containers=recipe_data_item.get('allowed_containers', [])
            )

            # Auto-detect container requirements
            ingredients_data = recipe_data_item.get('ingredients', [])
            if any(ing.get('type') == 'container' for ing in ingredients_data):
                recipe.requires_containers = True

            db.session.add(recipe)
            db.session.flush()  # Get recipe ID

            # Add ingredients using proper workflow
            ingredient_count = 0
            missing_ingredients = []
            
            for ing_data in ingredients_data:
                inventory_item = InventoryItem.query.filter_by(
                    name=ing_data['inventory_item_name']
                ).first()
                
                if not inventory_item:
                    missing_ingredients.append(ing_data['inventory_item_name'])
                    continue

                # Create recipe ingredient relationship
                recipe_ingredient = RecipeIngredient(
                    recipe_id=recipe.id,
                    inventory_item_id=inventory_item.id,
                    amount=ing_data['amount'],
                    unit=ing_data['unit']
                )
                
                db.session.add(recipe_ingredient)
                ingredient_count += 1

            if missing_ingredients:
                print(f"[WARNING] Recipe '{recipe.name}' missing ingredients: {', '.join(missing_ingredients)}")

            print(f"[ADDED] Recipe '{recipe.name}' with {ingredient_count}/{len(ingredients_data)} ingredients")
            created_count += 1

        db.session.commit()
        print(f"✅ Recipe startup complete: {created_count} recipes created, {skipped_count} skipped")
        return True

if __name__ == '__main__':
    startup_recipe_service()
