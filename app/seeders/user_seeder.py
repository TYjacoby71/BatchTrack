
from ..models import User, Organization
from ..extensions import db
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
    
    # Create developer user if it doesn't exist
    if not User.query.filter_by(username='admin').first():
        developer_user = User(
            username='admin',
            password_hash=generate_password_hash('admin'),
            role='developer',
            first_name='Jacob',
            last_name='Boulette',
            email='jacobboulette@outlook.com',
            phone='775-934-5968',
            organization_id=org.id,
            is_owner=True  # Set as organization owner
        )
        db.session.add(developer_user)
        print("✅ Created developer user: admin/admin")
    else:
        print("ℹ️  Developer user already exists")
    
    db.session.commit()
    print("✅ User seeding completed")
