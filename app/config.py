import os
import secrets

def generate_secret_key():
    """Generate a secure random secret key"""
    return secrets.token_hex(32)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or generate_secret_key()
    # Use PostgreSQL in production, SQLite for development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///batchtrack.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Payment Configuration
    # Stripe Configuration (legacy)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Whop Configuration (preferred)
    WHOP_SECRET_KEY = os.environ.get('WHOP_SECRET_KEY')
    WHOP_STORE_ID = os.environ.get('WHOP_STORE_ID')

    # OAuth Configuration
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

    # Debug configuration
    print(f"DEBUG: STRIPE_SECRET_KEY configured: {bool(STRIPE_SECRET_KEY)}")
    print(f"DEBUG: STRIPE_PUBLISHABLE_KEY configured: {bool(STRIPE_PUBLISHABLE_KEY)}")
    print(f"DEBUG: STRIPE_WEBHOOK_SECRET configured: {bool(STRIPE_WEBHOOK_SECRET)}")
    print(f"DEBUG: GOOGLE_OAUTH configured: {bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)}")
    print(f"DEBUG: EMAIL configured: {bool(MAIL_USERNAME and MAIL_PASSWORD)}")

    # Stripe Price IDs for subscription tiers
    STRIPE_PRICE_IDS = {
        'solo': os.environ.get('STRIPE_SOLO_PRICE_ID', ''),
        'team': os.environ.get('STRIPE_TEAM_PRICE_ID', ''),
        'enterprise': os.environ.get('STRIPE_ENTERPRISE_PRICE_ID', '')
    }

# Stripe Configuration
# Example of how to structure your Stripe price IDs and metadata
# STRIPE_PRICE_IDS = {
#     'solo': 'price_1234567890abcdef',
#     'solo_yearly': 'price_0987654321fedcba',
#     'team': 'price_abcdef1234567890',
#     'team_yearly': 'price_fedcba0987654321',
#     'enterprise': 'price_567890abcdef1234',
#     'enterprise_yearly': 'price_321fedcba0987654'
# }

# In your Stripe dashboard, add metadata to products:
# - features: "Feature 1,Feature 2,Feature 3"
# - user_limit: "10"
# - badge: "Most Popular"