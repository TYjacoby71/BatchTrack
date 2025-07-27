import stripe
import logging
from flask import current_app
from ..services.stripe_service import StripeService

logger = logging.getLogger(__name__)

class PricingService:
    """Service for handling subscription pricing and Stripe integration"""

    @staticmethod
    def get_pricing_data():
        """Get pricing data from Stripe with graceful fallbacks and tier-level resilience"""
        final_pricing_data = {}
        
        # Always try to get live Stripe data first
        try:
            pricing_data = PricingService._get_stripe_pricing()
            if pricing_data:
                final_pricing_data.update(pricing_data)
                logger.info(f"Successfully retrieved pricing for {len(pricing_data)} tiers from Stripe")
        except Exception as e:
            logger.error(f"Failed to get Stripe pricing data: {str(e)}")
        
        # If we don't have complete data, try cached snapshots for missing tiers
        all_tiers = PricingService._load_tiers_config()
        missing_tiers = []
        
        for tier_key, tier_data in all_tiers.items():
            if not isinstance(tier_data, dict):
                continue
            if not (tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True)):
                continue
            if tier_key not in final_pricing_data:
                missing_tiers.append(tier_key)
        
        if missing_tiers:
            logger.info(f"Trying cached snapshots for missing tiers: {missing_tiers}")
            try:
                snapshot_data = PricingService._get_snapshot_pricing_data()
                for tier_key in missing_tiers:
                    if tier_key in snapshot_data:
                        final_pricing_data[tier_key] = snapshot_data[tier_key]
                        logger.info(f"Retrieved tier {tier_key} from cached snapshots")
            except Exception as e:
                logger.error(f"Failed to get cached pricing data: {str(e)}")
        
        # For any remaining missing tiers, use configuration fallback
        still_missing = [tier for tier in missing_tiers if tier not in final_pricing_data]
        if still_missing:
            logger.info(f"Using configuration fallback for remaining tiers: {still_missing}")
            fallback_data = PricingService._get_fallback_pricing()
            for tier_key in still_missing:
                if tier_key in fallback_data:
                    final_pricing_data[tier_key] = fallback_data[tier_key]
                    logger.info(f"Using fallback data for tier {tier_key}")
        
        logger.info(f"Final pricing data assembled for {len(final_pricing_data)} tiers")
        return final_pricing_data

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

        # Start with fallback data structure - ensure we always have something for each tier
        pricing_data = {}
        successful_tiers = 0
        failed_tiers = 0
        
        for tier_key, tier_data in all_tiers.items():
            # Skip if tier_data is not a dictionary
            if not isinstance(tier_data, dict):
                continue
            if not (tier_data.get('is_customer_facing', True) and tier_data.get('is_available', True)):
                continue

            # Always start with fallback data - guarantees we have something
            pricing_data[tier_key] = PricingService._get_tier_fallback_data(tier_key, tier_data)

            lookup_key = tier_data.get('stripe_lookup_key')
            if not lookup_key:
                logger.info(f"Tier {tier_key} has no Stripe lookup key - using fallback only")
                continue

            logger.info(f"Looking up Stripe product for tier {tier_key} with lookup_key: {lookup_key}")

            try:
                # Search for prices using lookup key, then get the product
                prices = stripe.Price.list(lookup_keys=[lookup_key], limit=1, active=True)
                
                logger.info(f"Found {len(prices.data)} prices for lookup_key: {lookup_key}")

                if prices.data:
                    price = prices.data[0]
                    product = stripe.Product.retrieve(price.product)

                    # Update with Stripe data - overlay on top of fallback
                    pricing_data[tier_key].update({
                        'name': product.name or tier_data.get('name', tier_key.title()),
                        'price': f"${price.unit_amount / 100:.0f}",
                        'description': product.description or tier_data.get('description', f"Perfect for {tier_key} operations"),
                        'stripe_lookup_key': lookup_key,
                        'stripe_price_id_monthly': price.id if price.recurring and price.recurring.interval == 'month' else None,
                        'stripe_product_id': product.id,
                        'is_stripe_ready': True,
                        'is_fallback': False
                    })

                    successful_tiers += 1
                    logger.info(f"Successfully loaded Stripe pricing for {tier_key}: ${price.unit_amount / 100:.0f}")
                else:
                    logger.warning(f"No Stripe price found for lookup_key: {lookup_key} - using fallback for {tier_key}")
                    failed_tiers += 1

            except stripe.error.StripeError as e:
                logger.error(f"Stripe error for tier {tier_key}: {str(e)} - using fallback")
                failed_tiers += 1
            except Exception as e:
                logger.error(f"Unexpected error for tier {tier_key}: {str(e)} - using fallback")
                failed_tiers += 1

        logger.info(f"Pricing retrieval complete: {successful_tiers} tiers from Stripe, {failed_tiers} using fallback, {len(pricing_data)} total available")
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