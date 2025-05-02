
import json
from app import app, db
from models import Recipe, RecipeIngredient, InventoryItem

JSON_PATH = 'recipes_export_20250430_235506 (1).json'

def load_legacy_recipes():
    with app.app_context():
        with open(JSON_PATH, 'r') as f:
            recipe_data = json.load(f)

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
            db.session.add(recipe)
            db.session.flush()  # Assigns recipe.id

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

            print(f"[ADDED] Recipe '{recipe.name}' with {len(r['ingredients'])} ingredients.")

        db.session.commit()
        print("✅ Legacy recipe import complete.")

if __name__ == '__main__':
    load_legacy_recipes()
