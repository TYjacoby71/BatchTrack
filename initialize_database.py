
#!/usr/bin/env python3
"""
Script to properly initialize the database with all required tables and columns
"""
import os
from app import create_app, db
from app.models import *

def initialize_database():
    """Initialize the database with all required tables"""
    app = create_app()
    
    with app.app_context():
        try:
            # Create the instance directory if it doesn't exist
            os.makedirs('instance', exist_ok=True)
            
            # Drop all tables and recreate them
            print("🗑️  Dropping existing tables...")
            db.drop_all()
            
            # Create all tables with current schema
            print("🏗️  Creating all tables...")
            db.create_all()
            
            # Seed basic data
            print("🌱 Seeding basic data...")
            from app.seeders.role_permission_seeder import seed_roles_and_permissions
            from app.seeders.unit_seeder import seed_units
            from app.seeders.ingredient_category_seeder import seed_categories
            from app.seeders.user_seeder import seed_users
            
            seed_roles_and_permissions()
            seed_units()
            seed_categories()
            seed_users()
            
            db.session.commit()
            
            print("✅ Database initialized successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error initializing database: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    initialize_database()
