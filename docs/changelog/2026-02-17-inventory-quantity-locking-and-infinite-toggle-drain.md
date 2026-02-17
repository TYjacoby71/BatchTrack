## Summary
- Locked quantity-edit surfaces when an organization tier does not include `inventory.track_quantities`.
- Kept item creation available in locked tiers while forcing infinite-mode defaults and suppressing opening quantity input.
- Added explicit infinite-toggle drain behavior so switching tracked -> infinite zeros remaining lot quantities and logs an audit event.

## Problems Solved
- Users in quantity-locked tiers could still reach quantity-centric UI paths (update/recount/adjust) that should be upgrade-gated.
- Existing tracked items switching to infinite mode did not have a deterministic lot-drain policy.
- Quantity recount requests were not consistently blocked server-side when quantity tracking was unavailable.

## Key Changes
- `app/blueprints/inventory/routes.py`
  - `adjust_inventory` now hard-blocks quantity adjustments when the org tier lacks `inventory.track_quantities`.
  - `edit_inventory` now:
    - only performs recount when quantity actually changes,
    - blocks changed-quantity recounts when the tier lacks quantity tracking.
  - Inventory list serialization now projects effective tracking (`item.is_tracked && org_tracks_inventory_quantities`) for UI rendering.
- `app/services/inventory_adjustment/_creation_logic.py`
  - Forced opening quantity to `0` when org quantity tracking is unavailable.
  - Added cost-entry fallback so "total cost" submissions in forced-infinite mode are interpreted safely as per-unit cost.
- `app/services/inventory_adjustment/_edit_logic.py`
  - Added `_drain_lots_for_infinite_mode(...)` helper.
  - `update_inventory_item(...)` now supports:
    - `updated_by` audit attribution,
    - confirmation gate (`confirm_infinite_drain`) for user-driven tracked -> infinite toggles,
    - lot draining + `toggle_infinite_drain` history event logging.
- `app/templates/inventory_list.html`
  - Added tier-aware JS gate that bounces quantity-update actions to upgrade modal.
  - Forced create forms into infinite-mode setup by hiding quantity input and normalizing cost entry UX.
- `app/static/js/inventory/inventory_view.js`
  - Added view-page lock UX for quantity adjustment cards and expired-quantity action buttons.
  - Locked recount quantity input in edit modal for quantity-locked tiers with upgrade bounce behavior.
  - Added tracked -> infinite confirmation prompt wiring (`confirm_infinite_drain` hidden input injection).
- `app/templates/pages/inventory/view.html`
  - Persisted fetched modal state attributes for robust recount/toggle change detection in JS.
- `tests/test_inventory_adjustment_initial_stock.py`
  - Added regression test ensuring tracked -> infinite toggle drains active lots and records a drain history event.

## Files Modified
- `app/blueprints/inventory/routes.py`
- `app/services/inventory_adjustment/_creation_logic.py`
- `app/services/inventory_adjustment/_edit_logic.py`
- `app/templates/inventory_list.html`
- `app/static/js/inventory/inventory_view.js`
- `app/templates/pages/inventory/view.html`
- `tests/test_inventory_adjustment_initial_stock.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/2026-02-17-inventory-quantity-locking-and-infinite-toggle-drain.md`
