
#!/usr/bin/env python3
"""
Master seeder script - seeds everything in proper order
Run this to initialize a fresh database with all required data
"""

from app import create_app
from app.seeders import (
    seed_consolidated_permissions,
    seed_units,
    seed_users,
    seed_categories,
    seed_subscriptions
)
from app.seeders.user_seeder import update_existing_users_with_roles

def main():
    """Main seeder function"""
    app = create_app()
    
    with app.app_context():
        print("🚀 Starting BatchTrack Database Initialization")
        print("=" * 50)
        
        try:
            # 1. Seed permissions and roles first
            print("1️⃣  Seeding permissions and roles...")
            seed_consolidated_permissions()
            print()
            
            # 2. Seed measurement units
            print("2️⃣  Seeding measurement units...")
            seed_units()
            print()
            
            # 3. Seed users and organizations
            print("3️⃣  Seeding users and organizations...")
            seed_users()
            print()
            
            # 4. Seed ingredient categories
            print("4️⃣  Seeding ingredient categories...")
            from app.models import Organization
            org = Organization.query.first()
            if org:
                seed_categories(organization_id=org.id)
            else:
                print('❌ No organization found for seeding categories')
                return
            print()
            
            # 5. Update user roles
            print("5️⃣  Updating user role assignments...")
            update_existing_users_with_roles()
            print()
            
            # 6. Seed subscription data
            print("6️⃣  Seeding subscription data...")
            seed_subscriptions()
            print()
            
            print("=" * 50)
            print("✅ BatchTrack Database Initialization Complete!")
            print()
            print("🎯 Ready to go! You can now:")
            print("   • Login as 'admin' / 'admin' (Organization Owner)")
            print("   • Login as 'dev' / 'dev123' (System Developer)")
            print("   • Login as 'manager' / 'manager123' (Team Member)")
            print("   • Login as 'operator' / 'operator123' (Team Member)")
            
        except Exception as e:
            print(f"❌ Seeding failed: {str(e)}")
            raise

if __name__ == "__main__":
    main()
