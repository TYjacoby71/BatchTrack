
from app import app, db
from models import InventoryItem, IngredientCategory
import json

def update_ingredient_densities():
    with app.app_context():
        # Load density reference data
        with open('data/density_reference.json', 'r') as f:
            data = json.load(f)
            densities = {item['name'].lower(): item['density_g_per_ml'] 
                        for item in data['common_densities']}

        # Update all ingredients
        ingredients = InventoryItem.query.all()
        for ing in ingredients:
            if ing.density is None:  # Only update if density is not set
                name_lower = ing.name.lower()
                if name_lower in densities:
                    ing.density = densities[name_lower]
                    print(f"[UPDATED] {ing.name} → {ing.density} g/mL")
                else:
                    # Set water density (1.0) as default for volume ingredients
                    if ing.unit in ['ml', 'liter', 'gallon', 'floz']:
                        ing.density = 1.0
                        print(f"[DEFAULT] {ing.name} → 1.0 g/mL")

        db.session.commit()
        print("✅ Density update complete")

if __name__ == '__main__':
    update_ingredient_densities()
