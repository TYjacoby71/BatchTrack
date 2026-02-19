## Summary
Fixed the developer users-page password-change modal flow by moving it to a developer-scoped JSON endpoint that does not depend on customer settings permissions.

## Problems Solved
- Developers received a generic "Network error occurred" alert when changing password from `/developer/users`.
- The modal posted to `/settings/password/change`, which can redirect for developer contexts and break JSON parsing in the modal script.
- The users-page payload and endpoint expectations were fragile across mixed password field naming.

## Key Changes
- Added a new developer-only endpoint:
  - `POST /developer/api/profile/change-password`
- Added `UserService.update_own_password(...)` to validate:
  - required fields
  - current password correctness
  - new/confirm password match
  - minimum password length
- Updated the developer users-page modal JS to call the new developer endpoint.
- Added regression tests for:
  - successful developer password change
  - rejection when current password is incorrect

## Files Modified
- `app/blueprints/developer/views/user_routes.py`
- `app/services/developer/user_service.py`
- `app/templates/developer/users.html`
- `tests/developer/test_developer_routes.py`
- `docs/system/APP_DICTIONARY.md`
