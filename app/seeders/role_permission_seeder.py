"""Legacy seeder - redirects to consolidated permissions system"""

def seed_permissions():
    """Seed all permissions using consolidated permissions system"""
    print("⚠️  This is a legacy seeder.")
    print("Please run 'python seed_consolidated_permissions.py' instead.")
    print("This will use the new consolidated permissions structure with better organization.")

def seed_roles():
    """Seed system roles"""
    print("⚠️  This is a legacy seeder.")
    print("Please run 'python seed_consolidated_permissions.py' instead.")
    print("This will create all necessary roles with proper permissions.")

def seed_roles_and_permissions():
    """Main function for seeding roles and permissions"""
    print("⚠️  This is a legacy seeder.")
    print("Please run 'python seed_consolidated_permissions.py' instead.")
    print("This will set up the complete consolidated permissions system.")

if __name__ == '__main__':
    from .. import create_app
    app = create_app()
    with app.app_context():
        seed_roles_and_permissions()