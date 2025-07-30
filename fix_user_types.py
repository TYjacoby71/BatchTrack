
#!/usr/bin/env python3

from app import create_app
from app.models import User
from app.extensions import db

def fix_user_types():
    """Fix existing users with incorrect types/organization assignments"""
    app = create_app()
    
    with app.app_context():
        print("=== Fixing User Types and Organization Assignments ===")
        
        # Fix developer users
        dev_users = User.query.filter_by(user_type='developer').all()
        for user in dev_users:
            if user.organization_id is not None:
                print(f"⚠️  Developer user {user.username} has organization_id={user.organization_id} - fixing")
                user.organization_id = None
                db.session.add(user)
            else:
                print(f"✅ Developer user {user.username} correctly has no organization")
        
        # Check for users with organization but wrong type
        org_users = User.query.filter(User.organization_id.isnot(None)).all()
        for user in org_users:
            if user.user_type != 'customer':
                print(f"⚠️  User {user.username} has organization_id but user_type='{user.user_type}' - fixing to 'customer'")
                user.user_type = 'customer'
                db.session.add(user)
            else:
                print(f"✅ Organization user {user.username} correctly has user_type='customer'")
        
        # Check for customer users without organization
        customer_users = User.query.filter_by(user_type='customer').all()
        for user in customer_users:
            if user.organization_id is None:
                print(f"❌ CRITICAL: Customer user {user.username} has no organization_id!")
                print(f"   This user needs to be assigned to an organization or changed to developer type")
        
        db.session.commit()
        print("✅ User type fixes applied")
        
        # Summary
        print("\n📊 Summary:")
        print(f"Developer users: {User.query.filter_by(user_type='developer').count()}")
        print(f"Customer users: {User.query.filter_by(user_type='customer').count()}")
        print(f"Users with organization: {User.query.filter(User.organization_id.isnot(None)).count()}")
        print(f"Users without organization: {User.query.filter(User.organization_id.is_(None)).count()}")

if __name__ == '__main__':
    fix_user_types()
