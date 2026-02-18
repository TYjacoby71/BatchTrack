## Summary
Improved auth-email verification reliability and messaging so login flows no longer claim a verification email was sent when delivery fails.

## Problems Solved
- Required-mode login could display "We sent you a verification link" even when no email was delivered.
- Postmark/SendGrid provider readiness checks could appear "configured" without a valid sender address.
- Verification-send failures were harder to diagnose from login behavior alone.

## Key Changes
- Updated login verification send helper to return real delivery outcome from `EmailService.send_verification_email(...)`.
- Updated required-mode login messaging to:
  - confirm delivery only when send succeeds
  - show a delivery-failed warning when send fails and direct users to resend/provider checks
- Tightened `EmailService.is_configured()` for provider-backed sending:
  - SendGrid now requires `SENDGRID_API_KEY` **and** sender address
  - Postmark now requires `POSTMARK_SERVER_TOKEN` **and** sender address
- Added warning logging when verification-email delivery fails.
- Added regression test to ensure required-mode messaging does not claim delivery on send failure.

## Files Modified
- `app/services/email_service.py`
- `app/blueprints/auth/login_routes.py`
- `tests/test_auth_email_security.py`
