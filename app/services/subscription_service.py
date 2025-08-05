

# This service has been consolidated into BillingService
# All subscription management functionality is now handled by:
# - BillingService.create_subscription_for_organization()
# - BillingService.can_add_users()
# - BillingService.create_pending_subscription()
# - BillingService.create_exempt_subscription()
# - BillingService.validate_permission_for_tier()
# - BillingService.check_expired_trials()
# - BillingService.get_trial_status()
# - BillingService.extend_trial()

# This file can be safely deleted after updating all imports

