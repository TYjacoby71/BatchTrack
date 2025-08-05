# This service has been consolidated into BillingService
# All pricing functionality is now handled by:
# - BillingService.get_comprehensive_pricing_data()
# - BillingService.get_all_tiers_data()
# - BillingService.get_subscription_details()
# - BillingService.get_tier_features()
# - BillingService.get_user_limits()
# - BillingService._get_stripe_pricing()
# - BillingService._get_fallback_pricing()
# - BillingService._get_snapshot_pricing_data()

# This file can be safely deleted after updating all imports