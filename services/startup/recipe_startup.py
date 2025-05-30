
import json
from app import app, db
from models import Recipe, RecipeIngredient, InventoryItem

def load_startup_recipes():
    """Load startup recipes from export data"""
    with app.app_context():
        # Check if we have the legacy export file
        try:
            with open('recipes_export_20250430_235506 (1).json', 'r') as f:
                recipe_data = json.load(f)
        except FileNotFoundError:
            print("No recipe export file found - skipping recipe startup")
            return

        for r in recipe_data:
            if Recipe.query.filter_by(name=r['name']).first():
                print(f"[SKIPPED] Recipe '{r['name']}' already exists.")
                continue

            recipe = Recipe(
                name=r['name'],
                instructions=r.get('instructions', ''),
                label_prefix=r.get('label_prefix', ''),
                predicted_yield=r.get('predicted_yield', 0.0),
                predicted_yield_unit=r.get('predicted_yield_unit', 'count'),
                requires_containers=r.get('requires_containers', False),
                allowed_containers=r.get('allowed_containers', [])
            )
            
            # Auto-detect container requirements
            if any(i.get('type') == 'container' for i in r['ingredients']):
                recipe.requires_containers = True
                
            db.session.add(recipe)
            db.session.flush()

            ingredient_count = 0
            for ing in r['ingredients']:
                inventory_item = InventoryItem.query.filter_by(name=ing['inventory_item_name']).first()
                if not inventory_item:
                    print(f"[MISSING] Ingredient '{ing['inventory_item_name']}' not found — skipping.")
                    continue

                ri = RecipeIngredient(
                    recipe_id=recipe.id,
                    inventory_item_id=inventory_item.id,
                    amount=ing['amount'],
                    unit=ing['unit']
                )
                db.session.add(ri)
                ingredient_count += 1

            print(f"[ADDED] Recipe '{recipe.name}' with {ingredient_count} ingredients.")

        db.session.commit()
        print("✅ Startup recipe service complete")

if __name__ == '__main__':
    load_startup_recipes()
