
import os

class Config:
    # Your existing config...
    
    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    
    # Stripe Price IDs for each tier
    STRIPE_PRICE_IDS = {
        'solo': os.environ.get('STRIPE_SOLO_PRICE_ID'),
        'team': os.environ.get('STRIPE_TEAM_PRICE_ID'),
        'enterprise': os.environ.get('STRIPE_ENTERPRISE_PRICE_ID')
    }
