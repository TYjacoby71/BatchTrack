import stripe
import logging
from flask import current_app
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)

class PricingService:
    """Service for handling subscription pricing and Stripe integration"""

    @staticmethod
    def get_pricing_data():
        """Get pricing data from Stripe with graceful fallbacks"""
        # Always try to get live Stripe data first
        try:
            pricing_data = PricingService._get_stripe_pricing()
            if pricing_data:
                return pricing_data
        except Exception as e:
            logger.error(f"Failed to get Stripe pricing data: {str(e)}")
        
        # If Stripe fails, try cached snapshots from PricingSnapshot model
        logger.info("Stripe unavailable - trying cached pricing snapshots")
        try:
            snapshot_data = PricingService._get_snapshot_pricing_data()
            if snapshot_data:
                return snapshot_data
        except Exception as e:
            logger.error(f"Failed to get cached pricing data: {str(e)}")
        
        # Final fallback - use configuration data
        logger.info("No Stripe or snapshot data available - using configuration fallback")
        return PricingService._get_fallback_pricing()

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
    def _get_fallback_pricing():
        """Get fallback pricing from local configuration for customer-facing and available tiers only"""
        # Load dynamic tiers configuration
        all_tiers = PricingService._load_tiers_config()

        # Filter to only customer-facing and available tiers
        pricing_data = {}
        for tier_key, tier_data in all_tiers.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
            if tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True):
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
                    'is_stripe_ready': tier_data.get('is_stripe_ready', False),
                    'is_fallback': True
                }

        return pricing_data

    @staticmethod
    def _get_stripe_pricing():
        """Get comprehensive pricing data from Stripe for customer-facing and available tiers only"""
        import stripe
        import os
        
        # Check if Stripe is configured
        stripe_secret = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get('STRIPE_SECRET_KEY')
        if not stripe_secret:
            logger.warning("Stripe API key not configured")
            return {}
        
        # Set the API key
        stripe.api_key = stripe_secret
        
        # Load dynamic tiers configuration
        all_tiers = PricingService._load_tiers_config()

        # Start with fallback data structure
        pricing_data = {}
        for tier_key, tier_data in all_tiers.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
            if not (tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True)):
                continue

            lookup_key = tier_data.get('stripe_lookup_key')
            if not lookup_key:
                continue

            logger.info(f"Looking up Stripe product for tier {tier_key} with lookup_key: {lookup_key}")

            try:
                # Search for products using lookup key
                products = stripe.Product.search(
                    query=f"metadata['lookup_key']:'{lookup_key}'",
                    expand=['data.default_price']
                )

                logger.info(f"Found {len(products.data)} products for lookup_key: {lookup_key}")

                if products.data:
                    product = products.data[0]

                    # Get the default price
                    if product.default_price:
                        price = product.default_price

                        pricing_data[tier_key] = {
                            'name': product.name or tier_data.get('name', tier_key.title()),
                            'price': f"${price.unit_amount / 100:.0f}",
                            'features': tier_data.get('fallback_features', []),
                            'description': product.description or tier_data.get('description', f"Perfect for {tier_key} operations"),
                            'user_limit': tier_data.get('user_limit', 1),
                            'stripe_lookup_key': lookup_key,
                            'stripe_price_id_monthly': price.id if price.recurring and price.recurring.interval == 'month' else None,
                            'stripe_product_id': product.id,
                            'is_stripe_ready': True
                        }

                        logger.info(f"Successfully loaded pricing for {tier_key}: ${price.unit_amount / 100:.0f}")
                    else:
                        logger.warning(f"Product {product.id} has no default price")
                        # Fallback to config data
                        pricing_data[tier_key] = PricingService._get_tier_fallback_data(tier_key, tier_data)
                else:
                    logger.warning(f"No Stripe product found for lookup_key: {lookup_key}")
                    # Fallback to config data
                    pricing_data[tier_key] = PricingService._get_tier_fallback_data(tier_key, tier_data)

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error for tier {tier_key}: {str(e)}")
                # Fallback to config data
                pricing_data[tier_key] = PricingService._get_tier_fallback_data(tier_key, tier_data)
            except Exception as e:
                logger.error(f"Unexpected error for tier {tier_key}: {str(e)}")
                # Fallback to config data
                pricing_data[tier_key] = PricingService._get_tier_fallback_data(tier_key, tier_data)

        logger.info(f"Retrieved pricing for {len(pricing_data)} tiers from Stripe")
        return pricing_data

    @staticmethod
    def _get_tier_fallback_data(tier_key, tier_data):
        """Get fallback data structure for a single tier"""
        # Extract numeric price values for consistency with signup page expectations
        price_monthly = tier_data.get('fallback_price_monthly', 0)
        if isinstance(price_monthly, str):
            # Remove $ sign and convert to float
            price_monthly = float(price_monthly.replace('$', '').replace(',', '') or 0)
        
        price_yearly = tier_data.get('fallback_price_yearly', 0)
        if isinstance(price_yearly, str):
            # Remove $ sign and convert to float
            price_yearly = float(price_yearly.replace('$', '').replace(',', '') or 0)
        
        return {
            'name': tier_data.get('name', tier_key.title()),
            'price': f"${price_monthly:.0f}" if price_monthly > 0 else '$0',
            'price_display': f"${price_monthly:.0f}" if price_monthly > 0 else 'Free',
            'price_monthly': price_monthly,
            'price_yearly': price_yearly,
            'features': tier_data.get('fallback_features', []),
            'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
            'user_limit': tier_data.get('user_limit', 1),
            'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
            'is_stripe_ready': tier_data.get('is_stripe_ready', False),
            'is_fallback': True
        }

    @staticmethod
    def get_all_tiers_data():
        """Get all tiers data including internal/unavailable ones (for admin use)"""
        all_tiers = PricingService._load_tiers_config()

        # Convert to expected format but include all tiers
        pricing_data = {}
        for tier_key, tier_data in all_tiers.items():
            if not isinstance(tier_data, dict):
                continue

            pricing_data[tier_key] = PricingService._get_tier_fallback_data(tier_key, tier_data)
            # Add admin-specific fields
            pricing_data[tier_key].update({
                'is_customer_facing': tier_data.get('is_customer_facing', True),
                'is_available': tier_data.get('is_available', True)
            })

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

        # For now, we don't have a separate Subscription model with stripe_subscription_id
        # This would need to be implemented when you add the Subscription model
        return subscription_details

    @staticmethod
    def get_tier_features(tier):
        """Get features for a specific tier from config"""
        tiers_config = PricingService._load_tiers_config()
        tier_data = tiers_config.get(tier, {})
        return tier_data.get('fallback_features', [])

    @staticmethod
    def get_user_limits(tier):
        """Get user limits for each tier from config"""
        tiers_config = PricingService._load_tiers_config()
        tier_data = tiers_config.get(tier, {})
        return tier_data.get('user_limit', 1)

    @staticmethod
    def _get_tier_based_pricing_data():
        """Get pricing data from subscription tier configuration"""
        from ..blueprints.developer.subscription_tiers import load_tiers_config

        tiers_config = load_tiers_config()
        pricing_data = {}

        # Check if Stripe is properly configured
        import os
        stripe_secret = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get('STRIPE_SECRET_KEY')
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET') or current_app.config.get('STRIPE_WEBHOOK_SECRET')
        stripe_configured = bool(stripe_secret and webhook_secret)

        for tier_key, tier_data in tiers_config.items():
            # Only include customer-facing tiers
            if not tier_data.get('is_customer_facing', True):
                continue

            # Determine if tier should be stripe-ready based on configuration
            tier_is_stripe_ready = tier_data.get('is_stripe_ready', False)
            effective_stripe_ready = tier_is_stripe_ready and stripe_configured

            # Build pricing entry
            pricing_entry = {
                'name': tier_data.get('name', tier_key.title()),
                'price': tier_data.get('price_display', '$0'),
                'features': tier_data.get('fallback_features', []),
                'user_limit': tier_data.get('user_limit', 1),
                'is_stripe_ready': effective_stripe_ready
            }

            # Add monthly/yearly pricing if available
            if tier_data.get('stripe_price_monthly'):
                pricing_entry['price_monthly'] = float(tier_data['stripe_price_monthly'])
            if tier_data.get('stripe_price_yearly'):
                pricing_entry['price_yearly'] = float(tier_data['stripe_price_yearly'])

            pricing_data[tier_key] = pricing_entry

        return pricing_data

    @staticmethod
    def _get_snapshot_pricing_data():
        """Get pricing data from cached PricingSnapshot records when Stripe is unavailable"""
        try:
            from ..models.pricing_snapshot import PricingSnapshot
            from ..blueprints.developer.subscription_tiers import load_tiers_config
            
            tiers_config = load_tiers_config()
            pricing_data = {}
            
            for tier_key, tier_data in tiers_config.items():
                # Only include customer-facing and available tiers
                if not (tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True)):
                    continue
                
                # Try to get cached pricing from snapshots
                snapshot = PricingSnapshot.get_latest_for_tier(tier_key)
                
                if snapshot:
                    pricing_data[tier_key] = {
                        'name': tier_data.get('name', tier_key.title()),
                        'price': f"${snapshot.monthly_price:.0f}" if snapshot.monthly_price else '$0',
                        'price_yearly': f"${snapshot.yearly_price:.0f}" if snapshot.yearly_price else '$0',
                        'features': tier_data.get('fallback_features', []),
                        'description': tier_data.get('description', f"Perfect for {tier_key} operations"),
                        'user_limit': tier_data.get('user_limit', 1),
                        'stripe_lookup_key': tier_data.get('stripe_lookup_key', ''),
                        'is_stripe_ready': True,  # Snapshots are from Stripe data
                        'is_cached': True
                    }
                else:
                    # No snapshot available - tier unavailable for purchase
                    logger.warning(f"No pricing snapshot available for tier {tier_key}")
            
            logger.info(f"Retrieved cached pricing for {len(pricing_data)} tiers from snapshots")
            return pricing_data
            
        except Exception as e:
            logger.error(f"Failed to get cached pricing data: {str(e)}")
            return {}