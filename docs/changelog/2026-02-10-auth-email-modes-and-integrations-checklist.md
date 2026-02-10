# 2026-02-10 — Auth Email Modes, Legacy Fallback, and Integrations Checklist Alignment

## Summary
- Added environment-driven account email-security controls for verification and password reset flows.
- Implemented provider-aware fallback so environments without email credentials keep legacy signup/login behavior.
- Updated the developer integrations checklist to display configured vs effective auth-email mode and fallback state.
- Documented new auth-email controls in system docs and glossary entries.

## Problems Solved
- Operators could not safely enable auth-email security incrementally across environments.
- Integrations checklist did not surface effective auth-email behavior when provider credentials were absent.
- New auth/email concepts were not yet reflected in the dictionary and operational FAQ.

## Key Changes
- `app/config.py`
  - Added `AUTH_EMAIL_VERIFICATION_MODE`, `AUTH_EMAIL_REQUIRE_PROVIDER`, `AUTH_PASSWORD_RESET_ENABLED`, and `EMAIL_SMTP_ALLOW_NO_AUTH`.
- `app/services/email_service.py`
  - Added `get_verification_mode`, `should_issue_verification_tokens`, `should_require_verified_email_on_login`, and `password_reset_enabled`.
  - Tightened SMTP readiness checks to require sender + credentials unless explicitly allowed.
- `app/config_schema_parts/email.py`
  - Added schema/checklist support for auth-email toggles and token expiry controls.
- `app/blueprints/developer/views/integration_routes.py`
  - Added auth-email status payload (configured mode, effective mode, fallback, reset status).
  - Updated rate-limiter map entries for auth endpoints to current limits and source files.
  - Added maker-first metadata payload for integrations page title/description/canonical.
- `app/templates/developer/integrations.html`
  - Added account-email security callout showing effective mode and provider fallback.
- `docs/system/APP_DICTIONARY.md`
  - Added routes, services, UI, and operations terms for auth-email modes and reset/verification flows.
- `docs/system/OPERATIONS_AND_FAQ.md`
  - Added runbook section for account email-security mode selection and fallback behavior.

## Impact
- Teams can now run without email credentials during early rollout while keeping account flows usable.
- Production environments can enforce stronger behavior by toggling mode to `required`.
- Developer tooling and docs now match runtime behavior for auth-email security.

## Files Modified
- `app/config.py`
- `app/services/email_service.py`
- `app/config_schema_parts/email.py`
- `app/blueprints/developer/views/integration_routes.py`
- `app/templates/developer/integrations.html`
- `docs/system/APP_DICTIONARY.md`
- `docs/system/OPERATIONS_AND_FAQ.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-10-auth-email-modes-and-integrations-checklist.md` (this file)
