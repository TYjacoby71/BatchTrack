import json
from app import app, db
from models import Recipe, RecipeIngredient, InventoryItem

def load_startup_recipes():
    """Load startup recipes from export data"""
    with app.app_context():
        try:
            with open('recipes_export_20250430_235506 (1).json', 'r') as f:
                recipe_data = json.load(f)
        except FileNotFoundError:
            print("No recipe export file found - skipping recipe startup")
            return

        print("Loading startup recipes...")

        for r in recipe_data:
            if Recipe.query.filter_by(name=r['name']).first():
                print(f"[SKIPPED] Recipe '{r['name']}' already exists.")
                continue

            recipe = Recipe(
                name=r['name'],
                instructions=r.get('instructions', ''),
                label_prefix=r.get('label_prefix', ''),
                predicted_yield=float(r.get('predicted_yield', 0.0)),
                predicted_yield_unit=r.get('predicted_yield_unit', 'count'),
                requires_containers=bool(r.get('requires_containers', False)),
                allowed_containers=r.get('allowed_containers', [])
            )

            # Auto-detect container requirements
            if 'ingredients' in r and any(i.get('type') == 'container' for i in r['ingredients']):
                recipe.requires_containers = True

            db.session.add(recipe)
            db.session.flush()

            ingredient_count = 0
            if 'ingredients' in r:
                for ing in r['ingredients']:
                    # Try multiple possible field names for ingredient name
                    ingredient_name = (ing.get('inventory_item_name') or 
                                     ing.get('ingredient_name') or 
                                     ing.get('name', ''))

                    if not ingredient_name:
                        print(f"[WARNING] No ingredient name found in: {ing}")
                        continue

                    inventory_item = InventoryItem.query.filter_by(name=ingredient_name).first()
                    if not inventory_item:
                        print(f"[MISSING] Ingredient '{ingredient_name}' not found — skipping.")
                        continue

                    ri = RecipeIngredient(
                        recipe_id=recipe.id,
                        inventory_item_id=inventory_item.id,
                        amount=float(ing.get('amount', 0.0)),
                        unit=ing.get('unit', 'count')
                    )
                    db.session.add(ri)
                    ingredient_count += 1

            print(f"[ADDED] Recipe '{recipe.name}' with {ingredient_count} ingredients.")

        db.session.commit()
        print("✅ Startup recipe service complete")

if __name__ == '__main__':
    load_startup_recipes()