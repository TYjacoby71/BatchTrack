
#!/usr/bin/env python3
"""
Run the user seeder to create default users
"""
from app import create_app
from app.extensions import db
from seeders.user_seeder import seed_users

def main():
    """Run the user seeder"""
    print("🚀 Running user seeder...")
    
    app = create_app()
    with app.app_context():
        # Ensure tables exist
        db.create_all()
        
        # Run user seeder
        seed_users()
        
    print("✅ User seeder completed!")

if __name__ == "__main__":
    main()
