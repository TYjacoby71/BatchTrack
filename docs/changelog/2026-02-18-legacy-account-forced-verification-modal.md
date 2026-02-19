## Summary
Added an age-based verification enforcement path so older unverified accounts are blocked from login, get a fresh verification send attempt, and immediately see a modal explaining that verification is now required.

## Problems Solved
- Legacy accounts created before email verification was enabled could remain unverified without a clear forced-action flow.
- Prompt-mode login messaging alone did not provide an immediate, explicit "email sent + must verify" experience for older accounts.
- Users lacked a clear modal-based explanation when verification became mandatory due to account age policy.

## Key Changes
- Added age-based lock logic in login flow for unverified non-developer accounts:
  - default grace window is 10 days (`AUTH_EMAIL_FORCE_REQUIRED_AFTER_DAYS`, configurable in runtime config overrides)
  - once exceeded, login redirects to resend-verification instead of allowing dashboard access
- Preserved immediate verification send attempts on login and added explicit forced-lock warning copy for success/failure outcomes.
- Extended resend-verification page with an auto-opening modal (`forced=1`) that:
  - explains account-age enforcement
  - confirms whether a new verification email was sent
  - instructs users to verify before login continuation
- Added regression tests covering forced lock redirect behavior and modal rendering.

## Files Modified
- `app/blueprints/auth/login_routes.py`
- `app/templates/pages/auth/resend_verification.html`
- `tests/test_auth_email_security.py`
- `docs/system/APP_DICTIONARY.md`
