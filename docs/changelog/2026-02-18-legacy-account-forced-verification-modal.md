## Summary
Added an age-based legacy-account verification flow that force-sends a fresh verification email, allows login, and shows immediate in-app guidance with direct resend actions.

## Problems Solved
- Legacy accounts created before email verification was enabled could remain unverified without a clear forced-action flow.
- Prompt-mode login messaging alone did not provide an immediate, explicit "email sent + verify now" experience for older accounts.
- Users had no easy in-app place to request another verification email if the original message was missing/deleted/spammed.

## Key Changes
- Added age-based legacy-account logic in login flow for unverified non-developer accounts:
  - default grace window is 10 days (`AUTH_EMAIL_FORCE_REQUIRED_AFTER_DAYS`, configurable in runtime config overrides)
  - once exceeded in prompt mode, login force-sends a fresh verification attempt and queues an in-app modal after redirect
- Added a one-time global post-login modal for older unverified accounts that:
  - explains why a new verification email was sent
  - confirms send success/failure
  - provides direct resend + settings actions
- Added a persistent global in-app warning alert (for authenticated unverified users) with a direct resend-verification button.
- Added an explicit verification action card in Settings profile tab so users can always resend verification on demand.
- Added regression tests covering post-login modal queue/render behavior.

## Files Modified
- `app/blueprints/auth/login_routes.py`
- `app/templates/layout.html`
- `app/templates/settings/components/profile_tab.html`
- `app/templates/pages/auth/resend_verification.html`
- `tests/test_auth_email_security.py`
- `docs/system/APP_DICTIONARY.md`
