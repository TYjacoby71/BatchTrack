import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or generate_secret_key()
    # Use PostgreSQL in production, SQLite for development
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///batchtrack.db'

    # Your existing config...

    # Stripe Configuration (add your keys)
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Stripe Price IDs for subscription tiers (monthly and yearly)
    STRIPE_PRICE_IDS = {
        'solo_monthly': os.environ.get('STRIPE_SOLO_MONTHLY_PRICE_ID', ''),
        'solo_yearly': os.environ.get('STRIPE_SOLO_YEARLY_PRICE_ID', ''),
        'team_monthly': os.environ.get('STRIPE_TEAM_MONTHLY_PRICE_ID', ''),
        'team_yearly': os.environ.get('STRIPE_TEAM_YEARLY_PRICE_ID', ''),
        'enterprise_monthly': os.environ.get('STRIPE_ENTERPRISE_MONTHLY_PRICE_ID', ''),
        'enterprise_yearly': os.environ.get('STRIPE_ENTERPRISE_YEARLY_PRICE_ID', ''),
        # Legacy support for existing code
        'solo': os.environ.get('STRIPE_SOLO_MONTHLY_PRICE_ID', ''),
        'team': os.environ.get('STRIPE_TEAM_MONTHLY_PRICE_ID', ''),
        'enterprise': os.environ.get('STRIPE_ENTERPRISE_MONTHLY_PRICE_ID', '')
    }