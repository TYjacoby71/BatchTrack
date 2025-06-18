
from app.models import User, Organization, db
from werkzeug.security import generate_password_hash

def seed_users():
    """Seed default users into the database"""
    
    # Get or create default organization
    org = Organization.query.first()
    if not org:
        org = Organization(
            name="Jacob Boulette's Organization",
            subscription_tier='free'
        )
        db.session.add(org)
        db.session.flush()  # Get the ID
    
    # Create admin user if it doesn't exist
    if not User.query.filter_by(username='admin').first():
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin'),
            role='admin',
            first_name='Jacob',
            last_name='Boulette',
            email='jacobboulette@outlook.com',
            phone='775-934-5968',
            organization_id=org.id
        )
        db.session.add(admin_user)
        print("✅ Created admin user: admin/admin")
    else:
        print("ℹ️  Admin user already exists")
    
    # You can add more users here if needed
    # Example:
    # if not User.query.filter_by(username='testuser').first():
    #     test_user = User(
    #         username='testuser',
    #         password_hash=generate_password_hash('password'),
    #         role='user',
    #         first_name='Test',
    #         last_name='User',
    #         email='test@example.com',
    #         organization_id=org.id
    #     )
    #     db.session.add(test_user)
    #     print("✅ Created test user: testuser/password")
    
    db.session.commit()
    print("✅ User seeding completed")
