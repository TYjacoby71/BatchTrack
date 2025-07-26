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

        # Return empty dict if no config exists - should be created via admin interface
        logger.warning("No subscription_tiers.json found - tiers should be configured via developer interface")
        return {}

    @staticmethod
    def get_pricing_data():
        """Get pricing data from Stripe or fallback to default based on mode"""
        from flask import current_app

        logger.info("=== PRICING SERVICE ===")

        # Check if we're in development mode (no webhook secret = dev mode)
        is_dev_mode = not current_app.config.get('STRIPE_WEBHOOK_SECRET')
        logger.info(f"Development mode: {is_dev_mode}")

        # Try to initialize Stripe first
        from .stripe_service import StripeService
        stripe_initialized = StripeService.initialize_stripe()
        logger.info(f"Stripe initialization result: {stripe_initialized}")

        # In development mode, always use fallback pricing
        if is_dev_mode:
            logger.info("Development mode: Using fallback pricing data")
            pricing_data = PricingService._get_default_pricing()
            # Mark all tiers as not stripe-ready in dev mode
            for tier_data in pricing_data.values():
                tier_data['is_stripe_ready'] = False
            logger.info(f"Dev mode pricing data keys: {list(pricing_data.keys())}")
            return pricing_data

        # Production mode: Require Stripe
        if not stripe_initialized:
            logger.error("Production mode but Stripe not configured - returning empty pricing")
            return {}

        try:
            # Get pricing from Stripe
            logger.info("Production mode: Attempting to get Stripe pricing...")
            pricing_data = PricingService._get_stripe_pricing()
            # Mark all tiers as stripe-ready in production mode
            for tier_data in pricing_data.values():
                tier_data['is_stripe_ready'] = True
            logger.info(f"Production mode pricing data keys: {list(pricing_data.keys())}")
            return pricing_data
        except Exception as e:
            logger.error(f"Production mode: Failed to get Stripe pricing: {str(e)}")
            # In production, don't fallback - return empty to prevent access
            return {}

    @staticmethod
    def _get_default_pricing():
        """Get comprehensive pricing data from JSON file for customer-facing and available tiers only"""
        # Load dynamic tiers configuration
        all_tiers = PricingService._load_tiers_config()

        # Filter to only customer-facing and available tiers
        customer_tiers = {}
        for tier_key, tier_data in all_tiers.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
            if tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True):
                customer_tiers[tier_key] = tier_data

        # Filter to only customer-facing and available tiers
        pricing_data = {}
        for tier_key, tier_data in customer_tiers.items():
            # Use stripe pricing if available, otherwise fallback to configured pricing
            monthly_price = (tier_data.get('stripe_price_monthly') or 
                               tier_data.get('price_display') or 
                               tier_data.get('fallback_price_monthly', '$0'))
            yearly_price = (tier_data.get('stripe_price_yearly') or 
                              tier_data.get('price_yearly_display') or 
                              tier_data.get('fallback_price_yearly', '$0'))

            pricing_data[tier_key] = {
                'price': monthly_price,
                'price_yearly': yearly_price,
                'features': tier_data.get('fallback_features', tier_data.get('stripe_features', [])),
                'name': tier_data.get('name', tier_key.title()),
                'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
                'user_limit': tier_data.get('user_limit', 1),
                'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
                'is_stripe_ready': tier_data.get('is_stripe_ready', False)
            }

        return pricing_data

    @staticmethod
    def _get_stripe_pricing():
        """Get comprehensive pricing data from Stripe for customer-facing and available tiers only"""
        # Load dynamic tiers configuration
        all_tiers = PricingService._load_tiers_config()

        # Filter to only customer-facing and available tiers
        customer_tiers = {}
        for tier_key, tier_data in all_tiers.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
            if tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True):
                customer_tiers[tier_key] = tier_data

        # Filter to only customer-facing and available tiers
        pricing_data = {}
        for tier_key, tier_data in customer_tiers.items():
            # Use stripe pricing if available, otherwise fallback to configured pricing
            monthly_price = (tier_data.get('stripe_price_monthly') or 
                               tier_data.get('price_display') or 
                               tier_data.get('fallback_price_monthly', '$0'))
            yearly_price = (tier_data.get('stripe_price_yearly') or 
                              tier_data.get('price_yearly_display') or 
                              tier_data.get('fallback_price_yearly', '$0'))

            pricing_data[tier_key] = {
                'price': monthly_price,
                'price_yearly': yearly_price,
                'features': tier_data.get('fallback_features', tier_data.get('stripe_features', [])),
                'name': tier_data.get('name', tier_key.title()),
                'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
                'user_limit': tier_data.get('user_limit', 1),
                'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
                'is_stripe_ready': tier_data.get('is_stripe_ready', False)
            }

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
            # Use stripe pricing if available, otherwise fallback to configured pricing
            monthly_price = tier_data.get('stripe_price_monthly') or tier_data.get('price_display', '$0')
            yearly_price = tier_data.get('stripe_price_yearly') or tier_data.get('price_yearly_display', '$0')

            pricing_data[tier_key] = {
                'price': monthly_price,
                'price_yearly': yearly_price,
                'features': tier_data.get('fallback_features', tier_data.get('stripe_features', [])),
                'name': tier_data.get('name', tier_key.title()),
                'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
                'user_limit': tier_data.get('user_limit', 1),
                'is_customer_facing': tier_data.get('is_customer_facing', True),
                'is_available': tier_data.get('is_available', True),
                'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
                'is_stripe_ready': tier_data.get('is_stripe_ready', False)
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