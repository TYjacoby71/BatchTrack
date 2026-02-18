## Summary
Updated the developer integrations "test email" action to deliver messages to the support inbox instead of the currently logged-in developer account.

## Problems Solved
- Test sends could be missed when routed to whichever developer account clicked the button.
- Teams needed a stable, shared mailbox target for launch-readiness email checks.

## Key Changes
- Changed `/developer/integrations/test-email` to send to:
  - `SUPPORT_EMAIL` config value when present
  - fallback `support@batchtrack.com` otherwise
- Added validation for malformed support-recipient values and clearer error messaging.
- Updated route purpose/docstring to reflect support-mailbox behavior.

## Files Modified
- `app/blueprints/developer/views/integration_routes.py`
