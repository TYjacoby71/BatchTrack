# Stripe Cancellation During Customer Deletion

## Summary
Updated destructive deletion workflows so deleting a customer organization (or deleting the final customer user in an organization) attempts Stripe subscription cancellation first, and aborts deletion if cancellation fails.

## Problems Solved
- Customer deletion could remove account data while leaving active Stripe subscriptions running.
- Deletion workflows had no hard stop when Stripe cancellation failed, creating orphan billing risk.

## Key Changes
- Updated `BillingService.cancel_subscription` to:
  - inspect all subscription statuses for a Stripe customer,
  - cancel all non-canceled subscriptions,
  - treat already-canceled/no-subscription states as success (idempotent),
  - return failure only when Stripe cancellation calls fail.
- Updated `OrganizationService.delete_organization` to:
  - cancel Stripe subscriptions before any destructive delete work,
  - abort organization deletion if Stripe cancellation fails,
  - include cancellation confirmation in success messaging.
- Updated `UserService.hard_delete_user` to:
  - detect when the deleted user is the last non-deleted customer account in the org,
  - cancel the organization Stripe subscription first in that case,
  - abort hard delete if Stripe cancellation fails.
- Added tests for successful and failed cancellation gates in both organization and user hard-delete flows.

## Files Modified
- `app/services/billing_service.py`
- `app/services/developer/organization_service.py`
- `app/services/developer/user_service.py`
- `tests/developer/test_deletion_workflows.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`

## Impact
- Prevents accidental orphan Stripe subscriptions during customer teardown.
- Makes delete flows safer by requiring billing cleanup before destructive account deletion.
