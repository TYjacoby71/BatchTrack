
# BatchTrack Launch Checklist

**Target Launch Date: 7 Days**

## 🚨 Day 1-2: Stripe Setup & Configuration

### Step 1: Create Stripe Account
1. Go to [stripe.com](https://stripe.com) and create account
2. Complete business verification
3. Enable live payments (provide tax ID, bank account)

### Step 2: Create Products & Prices with Lookup Keys

In Stripe Dashboard → Products, create these exact products:

#### Free Tier
- **Product Name**: "BatchTrack Free"
- **Description**: "Free tier with limited features"
- **Price**: $0.00/month
- **Lookup Key**: `batchtrack_free_monthly`

#### Solo Tier
- **Product Name**: "BatchTrack Solo" 
- **Description**: "Perfect for individual makers"
- **Monthly Price**: $29.00/month
  - **Lookup Key**: `batchtrack_solo_monthly`
- **Yearly Price**: $290.00/year (2 months free)
  - **Lookup Key**: `batchtrack_solo_yearly`

#### Team Tier  
- **Product Name**: "BatchTrack Team"
- **Description**: "For small teams and growing businesses"
- **Monthly Price**: $79.00/month
  - **Lookup Key**: `batchtrack_team_monthly`
- **Yearly Price**: $790.00/year (2 months free)
  - **Lookup Key**: `batchtrack_team_yearly`

#### Enterprise Tier
- **Product Name**: "BatchTrack Enterprise"
- **Description**: "Advanced features for large operations"
- **Monthly Price**: $199.00/month
  - **Lookup Key**: `batchtrack_enterprise_monthly`
- **Yearly Price**: $1990.00/year (2 months free)
  - **Lookup Key**: `batchtrack_enterprise_yearly`

### Step 3: Get API Keys
1. Go to Developers → API Keys
2. Copy **Publishable key** (starts with `pk_`)
3. Copy **Secret key** (starts with `sk_`)
4. Create webhook endpoint (see Step 4)

### Step 4: Configure Webhook
1. Go to Developers → Webhooks
2. Add endpoint: `https://your-replit-url.replit.dev/billing/webhooks/stripe`
3. Select these events:
   - `customer.subscription.created`
   - `customer.subscription.updated` 
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copy webhook signing secret (starts with `whsec_`)

## 🔐 Day 1: Environment Variables Setup

Add these to Replit Secrets:

```
SECRET_KEY=your-secure-random-key-here
DATABASE_URL=postgresql://username:password@host:port/database
STRIPE_PUBLISHABLE_KEY=pk_test_or_pk_live_...
STRIPE_SECRET_KEY=sk_test_or_sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Stripe Price IDs (get these after creating products)
STRIPE_SOLO_PRICE_ID=price_...
STRIPE_TEAM_PRICE_ID=price_...
STRIPE_ENTERPRISE_PRICE_ID=price_...
STRIPE_SOLO_YEARLY_PRICE_ID=price_...
STRIPE_TEAM_YEARLY_PRICE_ID=price_...
STRIPE_ENTERPRISE_YEARLY_PRICE_ID=price_...
```

## 💾 Day 1: Database Migration

### Setup PostgreSQL
1. In Replit, go to Database tab
2. Create PostgreSQL database
3. Copy connection URL to `DATABASE_URL` secret

### Run Migrations
```bash
flask db upgrade
python -c "from app.seeders.role_permission_seeder import seed_roles_and_permissions; seed_roles_and_permissions()"
python -c "from app.seeders.unit_seeder import seed_units; seed_units()"
python -c "from app.seeders.ingredient_category_seeder import seed_categories; seed_categories()"
```

## 🔧 Day 2-3: Code Updates

### Update Config for Production
```python
# Add to app/config.py
import secrets

def generate_secret_key():
    return secrets.token_urlsafe(32)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or generate_secret_key()
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///batchtrack.db'
    
    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    # Stripe Price IDs
    STRIPE_PRICE_IDS = {
        'solo': os.environ.get('STRIPE_SOLO_PRICE_ID', ''),
        'team': os.environ.get('STRIPE_TEAM_PRICE_ID', ''),
        'enterprise': os.environ.get('STRIPE_ENTERPRISE_PRICE_ID', ''),
        'solo_yearly': os.environ.get('STRIPE_SOLO_YEARLY_PRICE_ID', ''),
        'team_yearly': os.environ.get('STRIPE_TEAM_YEARLY_PRICE_ID', ''),
        'enterprise_yearly': os.environ.get('STRIPE_ENTERPRISE_YEARLY_PRICE_ID', '')
    }
```

### Install Required Packages
Add to requirements.txt:
```
gunicorn==21.2.0
psycopg2-binary==2.9.7
stripe==6.5.0
```

## 🌐 Day 4: Domain Configuration

### Setup Custom Domain
1. In Replit, go to Deployments
2. Add custom domain: `batchtrack.com`
3. Configure DNS records as instructed
4. Enable SSL certificate

### Configure Production Deployment
Already set with: `gunicorn -w 4 -b 0.0.0.0:5000 run:app`

## ✅ Day 5-6: Critical Testing

### Test Signup Flow
1. Visit signup page
2. Create new organization
3. Verify trial subscription created
4. Check organization dashboard shows trial status

### Test Payment Flow
1. Go to upgrade page
2. Select Solo plan
3. Complete Stripe checkout
4. Verify subscription activated
5. Test webhook handling

### Test Core Features
1. **Batch Creation**: Create and start a batch
2. **FIFO Deduction**: Verify inventory deducted properly
3. **Multi-user Access**: Invite user, test permissions
4. **Recipe Scaling**: Test ingredient calculations

### Test Error Scenarios
1. Failed payment handling
2. Expired trial behavior
3. Subscription cancellation
4. Invalid webhook signatures

## 📋 Day 7: Pre-Launch Validation

### Performance Testing
```bash
# Install Apache Bench for load testing
pip install httpie

# Test with 10 concurrent users
http --session=test POST https://your-app.replit.dev/auth/login email=test@example.com password=testpass

# Monitor response times and error rates
```

### Security Checklist
- [ ] HTTPS enabled for all pages
- [ ] Stripe keys are in environment variables only
- [ ] Database credentials secured
- [ ] Rate limiting on auth endpoints
- [ ] CSRF protection enabled

### Legal Requirements
- [ ] Terms of Service created and linked
- [ ] Privacy Policy created and linked  
- [ ] Cookie policy (if using analytics)
- [ ] GDPR compliance notice (if EU users)

## 🚀 Launch Day Tasks

### Final Deployment
1. Switch Stripe to live mode
2. Update environment variables with live keys
3. Deploy to production
4. Test live payment flow
5. Monitor error logs

### Post-Launch Monitoring
1. Set up error tracking (Sentry recommended)
2. Monitor Stripe dashboard for payments
3. Watch application logs for errors
4. Test customer support flow

## 🔄 Week 1 Post-Launch

### Customer Success
- [ ] Welcome email flow working
- [ ] Trial expiration notifications
- [ ] Payment failure notifications
- [ ] Customer support email setup

### Analytics Setup
- [ ] Google Analytics installed
- [ ] Conversion funnel tracking
- [ ] Subscription metrics dashboard
- [ ] Customer usage analytics

## 🚨 Emergency Contacts & Procedures

### If Payments Fail
1. Check Stripe dashboard for errors
2. Verify webhook endpoint responding
3. Check application logs for Stripe errors
4. Contact Stripe support if needed

### If Site Goes Down
1. Check Replit deployment status
2. Check database connectivity
3. Review application logs
4. Scale up resources if needed

### Customer Support
- Response time goal: 4 hours
- Escalation path: Direct to developer
- Common issues documentation ready

## 📊 Success Metrics

### Week 1 Goals
- [ ] 50+ trial signups
- [ ] 10+ paid conversions
- [ ] <2% payment failure rate
- [ ] <1% critical bugs

### Month 1 Goals  
- [ ] 200+ trial signups
- [ ] 25+ active subscribers
- [ ] $2,000+ MRR
- [ ] 95%+ uptime

---

**⚠️ Critical Success Factors:**
1. Stripe integration must work flawlessly
2. Trial-to-paid conversion flow is smooth
3. Core batch tracking features are bug-free
4. Customer onboarding is intuitive
5. Payment failure handling is graceful

**🎯 Launch Readiness Checklist:**
- [ ] All environment variables set
- [ ] Database migrated and seeded
- [ ] Stripe products created with lookup keys
- [ ] Domain configured and SSL enabled
- [ ] Payment flow tested end-to-end
- [ ] Error monitoring in place
- [ ] Legal pages published
- [ ] Customer support ready
