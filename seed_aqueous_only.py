
#!/usr/bin/env python3
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.models import db
from app.seeders.seed_ingredients import seed_ingredients_from_files

def seed_aqueous_only():
    """Seed only the aqueous solutions blends file"""
    app = create_app()
    with app.app_context():
        selected_files = ['aqueous_solutions_blends.json']
        
        print("🔧 Seeding aqueous solutions & blends only...")
        print(f"📱 Processing file: {selected_files[0]}")
        
        try:
            categories_created, items_created = seed_ingredients_from_files(selected_files)
            
            db.session.commit()
            print(f"\n✅ Aqueous Solutions & Blends seeded successfully!")
            print(f"📊 Categories created: {categories_created}")
            print(f"📊 Items created: {items_created}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Seeding failed: {e}")
            raise

if __name__ == '__main__':
    seed_aqueous_only()
