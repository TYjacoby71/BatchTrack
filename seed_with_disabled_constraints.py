
#!/usr/bin/env python3
"""
Seed the database with all constraints temporarily disabled
This allows seeding to work even with missing foreign key relationships
"""

import os
import sys
from flask import Flask

# Add the current directory to Python path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import constraint disabling first
from temp_disable_constraints import patch_models_for_seeding

def create_seeding_app():
    """Create a minimal Flask app for seeding"""
    app = Flask(__name__)
    
    # Database configuration - use PostgreSQL if available, fallback to SQLite
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
        os.makedirs(instance_path, exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(instance_path, 'batchtrack.db')
    
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    return app

def run_seeders_safely():
    """Run all seeders with constraints disabled"""
    
    print("=== CONSTRAINT-DISABLED SEEDING ===")
    print("⚠️  Running with all foreign key constraints disabled")
    print("This is TEMPORARY for initial seeding only!")
    print()
    
    # Patch models to disable constraints
    patch_models_for_seeding()
    
    # Now import the app after patching
    app = create_seeding_app()
    
    from app.extensions import db
    db.init_app(app)
    
    with app.app_context():
        print("🔄 Running seeders in order...")
        
        try:
            # 1. Subscription tiers (must be first)
            print("\n1. Seeding subscription tiers...")
            from app.seeders.subscription_seeder import seed_subscriptions
            seed_subscriptions()
            
            # 2. Units
            print("\n2. Seeding units...")
            from app.seeders.unit_seeder import seed_units
            seed_units()
            
            # 3. Categories  
            print("\n3. Seeding ingredient categories...")
            from app.seeders.ingredient_category_seeder import seed_categories
            seed_categories()
            
            # 4. Users and organization (depends on subscription tiers)
            print("\n4. Seeding users and organization...")
            from app.seeders.user_seeder import seed_users_and_organization
            seed_users_and_organization()
            
            print("\n✅ ALL SEEDERS COMPLETED SUCCESSFULLY!")
            print("✅ Database is now seeded with initial data")
            print("\n⚠️  IMPORTANT: Constraints are still disabled in this session")
            print("   Restart the application for normal constraint enforcement")
            
        except Exception as e:
            print(f"\n❌ Seeding failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    success = run_seeders_safely()
    if success:
        print("\n🎉 Seeding completed! You can now run the application normally.")
        print("The constraints will be enforced again when you restart the app.")
    else:
        print("\n💥 Seeding failed. Check the errors above.")
        sys.exit(1)
