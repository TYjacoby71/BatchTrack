
from app import app, db
from models import InventoryItem, IngredientCategory

def get_category_keywords():
    return {
        'Oil': {
            'keywords': ['oil', 'tallow'],
            'exceptions': ['essential oil', 'fragrance oil']  # These go to Fragrance category
        },
        'Fragrance': {
            'keywords': ['essential oil', 'fragrance oil', 'perfume']
        },
        'Wax': {
            'keywords': ['wax', 'beeswax', 'paraffin']
        },
        'Liquid': {
            'keywords': ['water', 'juice', 'vinegar']
        },
        'Syrup': {
            'keywords': ['syrup', 'honey', 'agave']
        },
        'Clay': {
            'keywords': ['clay', 'bentonite', 'kaolin']
        },
        'Butter': {
            'keywords': ['butter', 'shea', 'cocoa butter', 'mango butter']
        }
    }

def assign_ingredient_categories():
    with app.app_context():
        categories = {c.name: c for c in IngredientCategory.query.all()}
        keywords = get_category_keywords()
        
        ingredients = InventoryItem.query.filter_by(type='ingredient').all()
        for ingredient in ingredients:
            if ingredient.category_id is not None:
                continue  # Skip if already categorized
                
            name_lower = ingredient.name.lower()
            assigned = False
            
            # First check for specific matches (with exceptions)
            for cat_name, rules in keywords.items():
                if 'exceptions' in rules:
                    if any(ex.lower() in name_lower for ex in rules['exceptions']):
                        continue
                        
                if any(kw.lower() in name_lower for kw in rules['keywords']):
                    ingredient.category = categories[cat_name]
                    print(f"[CATEGORIZED] {ingredient.name} → {cat_name}")
                    assigned = True
                    break
            
            # Default to "Other" if no match found
            if not assigned:
                ingredient.category = categories['Other']
                print(f"[DEFAULT] {ingredient.name} → Other")
                
        db.session.commit()
        print("✅ Category assignment complete")

if __name__ == '__main__':
    assign_ingredient_categories()
