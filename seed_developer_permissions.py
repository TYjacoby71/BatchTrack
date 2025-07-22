
#!/usr/bin/env python3
"""Seed developer permissions and roles"""

from app import create_app
from app.seeders.developer_permission_seeder import seed_developer_permissions, seed_developer_roles

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        print("Seeding developer permissions...")
        seed_developer_permissions()
        
        print("Seeding developer roles...")
        seed_developer_roles()
        
        print("Developer permission system seeded successfully!")
