# 2026-02-11 — Billing Access Policy Extraction + Inactive Organization Lockout

## Summary
- Fixed an auth/billing redirect-loop where blocked users could be bounced repeatedly to `/billing/upgrade`.
- Introduced a dedicated billing-access policy service so middleware remains transport-focused.
- Enforced hard-lock behavior for inactive/canceled/suspended organizations across both middleware and login flows.
- Added regression tests for upgrade-route loop prevention and hard-lock login/session behavior.

## Problems Solved
- Recoverable billing enforcement (`past_due`, `payment_failed`) could self-redirect on `/billing/upgrade`.
- Hard-locked organizations could still produce confusing auth behavior due to mixed policy logic in middleware.
- Billing access rules were duplicated across request-handling and login paths.

## Key Changes
- `app/services/billing_access_policy_service.py`
  - Added `BillingAccessPolicyService` with canonical decisions:
    - `allow`
    - `require_upgrade`
    - `hard_lock`
  - Added route exemption helper for billing endpoints.
- `app/middleware.py`
  - Refactored billing checks to consume policy decisions instead of local branching.
  - Keeps middleware responsibility to request behavior only (redirect/JSON/logout).
  - Hard-lock decisions invalidate session and redirect to login with clear support messaging.
- `app/blueprints/auth/login_routes.py`
  - Uses the same policy service to deny login when organization access is hard-locked.
- `tests/test_billing_and_tier_enforcement.py`
  - Updated expected redirects by billing status.
  - Added no-loop regression for `/billing/upgrade`.
  - Added login rejection test for inactive/canceled orgs.
- `tests/test_billing_access_policy_service.py`
  - Added focused unit coverage for decision mapping and route exemption logic.

## Documentation Updates
- `docs/system/APP_DICTIONARY.md`
  - Added entries for billing access policy decisions and inactive-org login lockout semantics.
- `docs/system/BILLING.md`
  - Added explicit policy-vs-middleware boundary and change-process guidance for access gating.
- `docs/system/SERVICES.md`
  - Added `BillingAccessPolicyService` as a first-class service authority.

## Impact
- Customers with recoverable billing issues are sent to upgrade flow without redirect loops.
- Customers in hard-lock states are cleanly blocked with deterministic logout/login messaging.
- Architecture now has a clearer division of authority: policy in service layer, HTTP behavior in middleware.
