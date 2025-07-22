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

    # Stripe Configuration (handle missing keys gracefully)
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Stripe Price IDs for subscription tiers
    STRIPE_PRICE_IDS = {
        'solo': os.environ.get('STRIPE_SOLO_PRICE_ID', ''),
        'team': os.environ.get('STRIPE_TEAM_PRICE_ID', ''),
        'enterprise': os.environ.get('STRIPE_ENTERPRISE_PRICE_ID', '')
    }