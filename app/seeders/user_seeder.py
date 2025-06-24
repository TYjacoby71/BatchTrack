
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
            is_owner=True  # Boolean value for organization owner
        )
        db.session.add(developer_user)
        print("✅ Created developer user: admin/admin")
    else:
        print("ℹ️  Developer user already exists")
    
    # Create a sample organization_owner (maker) user if it doesn't exist
    if not User.query.filter_by(username='maker').first():
        maker_user = User(
            username='maker',
            password_hash=generate_password_hash('maker123'),
            role='organization_owner',
            first_name='Sample',
            last_name='Maker',
            email='maker@example.com',
            phone='555-0123',
            organization_id=org.id,
            is_owner=False  # Boolean value - not the primary owner
        )
        db.session.add(maker_user)
        print("✅ Created sample maker user: maker/maker123")
    else:
        print("ℹ️  Sample maker user already exists")
    
    db.session.commit()
    print("✅ User seeding completed")
