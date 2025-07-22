
import stripe
import logging
from flask import current_app
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)

class PricingService:
    """Service for fetching pricing information from Stripe"""
    
    @staticmethod
    def get_pricing_data():
        """Get pricing data from Stripe for all tiers"""
        # Return hardcoded pricing if Stripe is not configured
        if not StripeService.initialize_stripe():
            logger.warning("Stripe not configured - using hardcoded pricing data")
            return {
                'solo': {'price': '$29', 'features': ['Up to 5 users', 'Full batch tracking', 'Email support']},
                'team': {'price': '$79', 'features': ['Up to 10 users', 'Advanced features', 'Custom roles']},
                'enterprise': {'price': '$199', 'features': ['Unlimited users', 'All features', 'API access']}
            }
        
        pricing_data = {
            'solo': {'price': '$29', 'features': ['Up to 5 users', 'Full batch tracking', 'Email support']},
            'team': {'price': '$79', 'features': ['Up to 10 users', 'Advanced features', 'Custom roles']},
            'enterprise': {'price': '$199', 'features': ['Unlimited users', 'All features', 'API access']}
        }
        
        try:
            # Get price IDs from config
            price_ids = current_app.config.get('STRIPE_PRICE_IDS', {})
            
            for tier, price_id in price_ids.items():
                if price_id:
                    try:
                        price = stripe.Price.retrieve(price_id)
                        product = stripe.Product.retrieve(price.product)
                        
                        # Format price (assumes monthly billing)
                        amount = price.unit_amount / 100  # Convert from cents
                        currency = price.currency.upper()
                        
                        pricing_data[tier]['price'] = f'${int(amount)}'
                        pricing_data[tier]['stripe_price_id'] = price_id
                        
                        # Get features from product metadata or description
                        if product.metadata.get('features'):
                            features_str = product.metadata['features']
                            pricing_data[tier]['features'] = features_str.split(',')
                        elif product.description:
                            # Parse description for features
                            pricing_data[tier]['description'] = product.description
                            
                    except stripe.error.StripeError as e:
                        logger.warning(f"Could not fetch Stripe data for {tier}: {str(e)}")
                        # Keep the hardcoded fallback
                        
        except Exception as e:
            logger.error(f"Error fetching pricing data: {str(e)}")
            # Return hardcoded fallbacks
            
        return pricing_data
    
    @staticmethod
    def get_tier_features(tier):
        """Get features for a specific tier"""
        features_map = {
            'free': ['Basic features', '1 user', 'Community support'],
            'solo': ['Up to 5 users', 'Full batch tracking', 'Basic inventory management', 'Email support'],
            'team': ['Up to 10 users', 'Advanced batch tracking', 'Full inventory management', 'Custom roles & permissions', 'Priority support'],
            'enterprise': ['Unlimited users', 'All features included', 'API access', 'Custom integrations', 'Phone & email support']
        }
        return features_map.get(tier, [])
    
    @staticmethod
    def get_user_limits(tier):
        """Get user limits for each tier"""
        limits = {
            'free': 1,
            'solo': 5,
            'team': 10,
            'enterprise': -1  # Unlimited
        }
        return limits.get(tier, 1)
