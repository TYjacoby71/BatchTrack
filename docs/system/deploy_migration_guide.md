
# Production Deployment & Migration Guide

## Initial Production Setup

1. **Clean Database Approach** (Recommended):
   - Deploy with empty database
   - Run migrations: `flask db upgrade`
   - Seed only production-ready data
   - Create initial admin/exempt organization

2. **Migrate Development Data**:
   - Export essential data (organizations, users you want to keep)
   - Deploy and run migrations
   - Import cleaned data

## Pushing Updates to Production

1. **Code Changes**: 
   - Commit changes to your Repl
   - Redeploy (Replit will automatically pull latest code)

2. **Database Schema Changes**:
   ```bash
   # Generate migration for model changes
   flask db migrate -m "Description of changes"
   
   # Apply to production database
   flask db upgrade
   ```

## Test Users & Billing

- **Exempt Organizations**: Will work without billing (tier = 'exempt')
- **Test Users**: Won't work in production without valid subscriptions
- **Development Mode**: Simulated subscriptions won't work in production

## Production Setup Commands

```bash
# Initialize production database
flask db upgrade

# Create exempt organization for admin access
python -c "
from app import create_app
from app.models import db, Organization, User, Subscription
from app.services.subscription_service import SubscriptionService

app = create_app()
with app.app_context():
    # Create exempt org
    org = Organization(name='Admin Organization', subscription_tier='exempt')
    db.session.add(org)
    db.session.flush()
    
    # Create exempt subscription
    SubscriptionService.create_exempt_subscription(org, 'Production admin access')
    
    # Create admin user
    admin = User(username='admin', email='admin@yourcompany.com', 
                 organization_id=org.id, is_organization_owner=True)
    admin.set_password('secure_password_here')
    db.session.add(admin)
    db.session.commit()
"
```
