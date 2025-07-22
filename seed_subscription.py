
#!/usr/bin/env python3

from app import create_app
from app.models import db, Organization, Subscription
from datetime import datetime

def seed_subscription():
    app = create_app()
    
    with app.app_context():
        # Check if org 1 exists and create subscription if missing
        org = Organization.query.get(1)
        if org:
            sub = Subscription.query.filter_by(organization_id=1).first()
            if not sub:
                print('Creating exempt subscription for organization 1')
                sub = Subscription(
                    organization_id=1,
                    tier='exempt',
                    status='active',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    notes='Reserved organization for owner and testing'
                )
                db.session.add(sub)
                db.session.commit()
                print('Created subscription successfully')
            else:
                print(f'Subscription already exists: {sub.tier}')
                if sub.tier != 'exempt':
                    sub.tier = 'exempt'
                    sub.status = 'active'
                    db.session.commit()
                    print('Updated to exempt tier')
        else:
            print('Organization 1 not found')

if __name__ == '__main__':
    seed_subscription()
