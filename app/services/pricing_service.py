import stripe
import logging
from flask import current_app
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)

class PricingService:
    """Service for fetching pricing information from Stripe"""

    @staticmethod
    def _load_tiers_config():
        """Load subscription tiers configuration from JSON file"""
        import os
        import json

        config_file = 'subscription_tiers.json'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)

        # Fallback to default configuration
        return {
            'solo': {
                'name': 'Solo Plan',
                'price_display': '$19',
                'price_yearly_display': '$190',
                'features': [
                    '1 user account',
                    'Complete batch tracking with FIFO',
                    'Recipe management and scaling',
                    'Expiration alerts and freshness tracking',
                    'Email support'
                ],
                'fallback_features': [
                    '1 user account',
                    'Complete batch tracking with FIFO',
                    'Recipe management and scaling',
                    'Expiration alerts and freshness tracking',
                    'Email support'
                ],
                'stripe_price_id': '',
                'user_limit': 1,
                'is_customer_facing': True,
                'is_available': True
            },
            'team': {
                'name': 'Team Plan',
                'price_display': '$29',
                'price_yearly_display': '$290',
                'features': [
                    'Up to 10 users',
                    'Everything in Solo Plan',
                    'Product catalog with variants',
                    'Team collaboration tools',
                    'Custom role management',
                    'Basic reporting and analytics',
                    'Priority email support'
                ],
                'fallback_features': [
                    'Up to 10 users',
                    'Everything in Solo Plan', 
                    'Product catalog with variants',
                    'Team collaboration tools',
                    'Custom role management',
                    'Basic reporting and analytics',
                    'Priority email support'
                ],
                'stripe_price_id': '',
                'user_limit': 10,
                'is_customer_facing': True,
                'is_available': True
            },
            'enterprise': {
                'name': 'Enterprise Plan',
                'price_display': '$99',
                'price_yearly_display': '$990',
                'features': [
                    'Unlimited users',
                    'Everything in Team Plan',
                    'Advanced reporting and analytics',
                    'API access for integrations',
                    'POS system integration',
                    'Dedicated account manager',
                    'Priority phone support'
                ],
                'fallback_features': [
                    'Unlimited users',
                    'Everything in Team Plan',
                    'Advanced reporting and analytics', 
                    'API access for integrations',
                    'POS system integration',
                    'Dedicated account manager',
                    'Priority phone support'
                ],
                'stripe_price_id': '',
                'user_limit': -1,
                'is_customer_facing': True,
                'is_available': True
            }
        }

    @staticmethod
    def get_pricing_data():
        """Get comprehensive pricing data from Stripe for customer-facing and available tiers only"""
        # Load dynamic tiers configuration
        all_tiers = PricingService._load_tiers_config()

        # Filter to only customer-facing and available tiers
        pricing_data = {}
        for tier_key, tier_data in all_tiers.items():
            # Only include tiers that are customer-facing and available
            if tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True):
                pricing_data[tier_key] = {
                    'price': tier_data.get('price_display', '$0'),
                    'price_yearly': tier_data.get('price_yearly_display', '$0'),
                    'features': tier_data.get('fallback_features', tier_data.get('features', [])),
                    'name': tier_data.get('name', tier_key.title()),
                    'description': f"Perfect for {tier_key} operations",
                    'user_limit': tier_data.get('user_limit', 1)
                }

        # Only try to fetch from Stripe if properly configured
        if not StripeService.initialize_stripe():
            logger.info("Stripe not configured, using default pricing data")
            return pricing_data

        try:
            # Get price IDs from config
            price_ids = current_app.config.get('STRIPE_PRICE_IDS', {})

            for tier, price_id in price_ids.items():
                if price_id:
                    try:
                        price = stripe.Price.retrieve(price_id)
                        product = stripe.Product.retrieve(price.product)

                        # Format price based on interval
                        amount = price.unit_amount / 100  # Convert from cents
                        currency = price.currency.upper()
                        interval = price.recurring.get('interval', 'month') if price.recurring else 'month'

                        # Store price information
                        price_key = 'price_yearly' if interval == 'year' else 'price'
                        pricing_data[tier][price_key] = f'${int(amount)}'
                        pricing_data[tier]['stripe_price_id'] = price_id
                        pricing_data[tier]['interval'] = interval

                        # Get product information
                        pricing_data[tier]['name'] = product.name or pricing_data[tier]['name']
                        pricing_data[tier]['description'] = product.description or pricing_data[tier]['description']

                        # Get features from product metadata
                        if product.metadata.get('features'):
                            features_str = product.metadata['features']
                            pricing_data[tier]['features'] = [f.strip() for f in features_str.split(',')]

                        # Get additional metadata
                        if product.metadata.get('user_limit'):
                            pricing_data[tier]['user_limit'] = product.metadata['user_limit']

                        if product.metadata.get('badge'):
                            pricing_data[tier]['badge'] = product.metadata['badge']

                        # Get product images
                        if product.images:
                            pricing_data[tier]['image'] = product.images[0]

                    except stripe.error.StripeError as e:
                        logger.warning(f"Could not fetch Stripe data for {tier}: {str(e)}")
                        # Keep the hardcoded fallback

        except Exception as e:
            logger.error(f"Error fetching pricing data: {str(e)}")
            # Return hardcoded fallbacks

        try:
            # Fetch active products from Stripe
            products = stripe.Product.list(active=True, expand=['data.default_price'])

            for product in products.data:
                # Check if this product has a lookup key that matches our tiers
                lookup_key = product.metadata.get('lookup_key', '')
                if lookup_key and lookup_key in pricing_data:

                    # Get prices for this product
                    prices = stripe.Price.list(product=product.id, active=True)
                    if prices.data:
                        price = prices.data[0]  # Get first active price

                        # Convert price from cents to dollars
                        amount = price.unit_amount / 100 if price.unit_amount else 0

                        # Update pricing data with Stripe information
                        pricing_data[lookup_key].update({
                            'price': f"${amount}",
                            'features': product.metadata.get('features', '').split(',') if product.metadata.get('features') else pricing_data[lookup_key]['features'],
                            'stripe_price_id': price.id,
                            'stripe_product_id': product.id
                        })

                        logger.info(f"Updated pricing for {lookup_key}: ${amount}")

        except stripe.error.StripeError as e:
            logger.warning(f"Failed to fetch Stripe pricing data: {str(e)}")
            # Continue with fallback pricing data

        return pricing_data

    @staticmethod
    def get_all_tiers_data():
        """Get all tiers data including internal/unavailable ones (for admin use)"""
        all_tiers = PricingService._load_tiers_config()

        # Convert to expected format but include all tiers
        pricing_data = {}
        for tier_key, tier_data in all_tiers.items():
            pricing_data[tier_key] = {
                'price': tier_data.get('price_display', '$0'),
                'price_yearly': tier_data.get('price_yearly_display', '$0'),
                'features': tier_data.get('fallback_features', tier_data.get('features', [])),
                'name': tier_data.get('name', tier_key.title()),
                'description': f"Perfect for {tier_key} operations",
                'user_limit': tier_data.get('user_limit', 1),
                'is_customer_facing': tier_data.get('is_customer_facing', True),
                'is_available': tier_data.get('is_available', True)
            }

        return pricing_data

    @staticmethod
    def get_subscription_details(organization):
        """Get detailed subscription information from Stripe"""
        subscription_details = {
            'tier': organization.effective_subscription_tier,
            'status': 'inactive',
            'next_billing_date': None,
            'amount': None,
            'interval': None,
            'trial_end': None,
            'cancel_at_period_end': False
        }

        if not organization.subscription or not organization.subscription.stripe_subscription_id:
            return subscription_details

        if not StripeService.initialize_stripe():
            return subscription_details

        try:
            stripe_subscription = stripe.Subscription.retrieve(
                organization.subscription.stripe_subscription_id
            )

            subscription_details.update({
                'status': stripe_subscription.status,
                'next_billing_date': stripe_subscription.current_period_end,
                'cancel_at_period_end': stripe_subscription.cancel_at_period_end,
                'trial_end': stripe_subscription.trial_end
            })

            # Get pricing details
            if stripe_subscription.items.data:
                item = stripe_subscription.items.data[0]
                price = item.price
                subscription_details.update({
                    'amount': price.unit_amount / 100,
                    'currency': price.currency.upper(),
                    'interval': price.recurring.interval if price.recurring else 'month'
                })

        except stripe.error.StripeError as e:
            logger.error(f"Failed to fetch subscription details: {str(e)}")

        return subscription_details

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