# 2026-02-11 — Deletion Hard-Delete Safety + Legacy Marketplace Archive

## Summary
- Replaced fragile organization hard-delete logic with a scoped safety pipeline.
- Added a dedicated developer hard-delete endpoint for non-developer users.
- Added legacy marketplace recipe JSON snapshot export before org deletion.
- Added cross-organization lineage/source detachment to prevent legacy recipe breakage after source org deletion.

## Problems Solved
- Organization hard-delete failed due to stale model imports (`Category` / missing subscription model assumptions).
- Existing org delete path could break external recipe lineage references after source org removal.
- Developer tools had soft-delete only for users and no explicit hard-delete workflow for test account cleanup.

## Key Changes
- `app/services/developer/deletion_utils.py` (new)
  - Added helpers to archive marketplace/listed/sold recipes to JSON.
  - Added helper to detach external recipe links pointing at deleted org recipes.
  - Added table-wide FK cleanup helper for user hard-delete safety.
  - Added FK-safe org-scoped table deletion helper.
- `app/services/developer/organization_service.py`
  - Replaced hard-delete flow with scoped, staged cleanup.
  - Removed stale imports and switched to explicit model cleanup by org/user/recipe IDs.
  - Integrated archive + link detachment summary in success response.
- `app/services/developer/user_service.py`
  - Added `hard_delete_user()` for permanent non-developer account deletion with FK cleanup.
- `app/blueprints/developer/views/user_routes.py`
  - Added `POST /developer/api/user/hard-delete`.
- `app/templates/components/shared/user_management_modal.html`
  - Added explicit “Hard Delete User (Test Only)” action with typed confirmation.
- `app/templates/developer/organization_detail.html`
  - Updated delete warning copy to indicate marketplace snapshots are archived before removal.
- `tests/developer/test_deletion_workflows.py` (new)
  - Added regression coverage for org hard-delete archive/detach behavior and user hard-delete safeguards.

## Documentation Alignment
- Updated `docs/system/APP_DICTIONARY.md` with new route, service, UI, and operations terms.
- Updated `docs/system/USERS_AND_PERMISSIONS.md` with developer deletion mode behavior.

## Impact
- Developer org deletion is now safer for production-like data shapes and preserves legacy marketplace continuity.
- Test-account cleanup can use a dedicated hard-delete path without broad tenant data destruction.
- Cross-tenant recipe references no longer retain stale links after source org deletion.

## Files Modified
- `app/services/developer/deletion_utils.py`
- `app/services/developer/organization_service.py`
- `app/services/developer/user_service.py`
- `app/blueprints/developer/views/user_routes.py`
- `app/templates/components/shared/user_management_modal.html`
- `app/templates/developer/organization_detail.html`
- `tests/developer/test_deletion_workflows.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/system/USERS_AND_PERMISSIONS.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `docs/changelog/2026-02-11-deletion-hard-delete-safety-and-legacy-archive.md` (this file)
