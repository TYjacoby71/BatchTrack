## Summary
- Split inventory quantity-tracking entitlement from batch output tracking so deduction behavior is controlled by an inventory-scoped permission.
- Added a new permission key, `inventory.track_quantities`, and assigned it to paid tiers in the tier seed JSON.
- Updated pricing/catalog presentation rows to show quantity tracking and batch output posting as separate capabilities.

## Problems Solved
- Inventory deduction quantity behavior was coupled to `batches.track_inventory_outputs`, which mixes two distinct concerns.
- Tier configuration could not independently represent:
  - on-hand quantity depletion behavior during deductions, and
  - whether batch completion can post product/intermediate outputs.
- Pricing presentation could not clearly explain the difference between quantity tracking and output posting.

## Key Changes
- Added `inventory.track_quantities` to `app/seeders/consolidated_permissions.json`.
- Added `inventory.track_quantities` to Solo/Team/Enterprise in `app/seeders/subscription_tiers.json`.
- Added new `app/services/inventory_tracking_policy.py` with canonical helper:
  - `org_allows_inventory_quantity_tracking(...)`
  - checks `inventory.track_quantities` first, with legacy fallback to `batches.track_inventory_outputs`.
- Switched inventory quantity-tracking checks to the inventory policy helper in:
  - `app/services/inventory_adjustment/_creation_logic.py`
  - `app/services/inventory_adjustment/_edit_logic.py`
  - `app/services/inventory_adjustment/_deductive_ops.py`
  - `app/services/inventory_adjustment/_fifo_ops.py`
  - `app/services/inventory_adjustment/_validation.py`
  - `app/services/stock_check/handlers/ingredient_handler.py`
  - `app/blueprints/inventory/routes.py`
- Split tier presentation rows in `app/services/tier_presentation/catalog.py`:
  - inventory quantity tracking from deductions
  - batch output posting to inventory

## Files Modified
- `app/services/inventory_tracking_policy.py`
- `app/seeders/consolidated_permissions.json`
- `app/seeders/subscription_tiers.json`
- `app/services/inventory_adjustment/_creation_logic.py`
- `app/services/inventory_adjustment/_edit_logic.py`
- `app/services/inventory_adjustment/_deductive_ops.py`
- `app/services/inventory_adjustment/_fifo_ops.py`
- `app/services/inventory_adjustment/_validation.py`
- `app/services/stock_check/handlers/ingredient_handler.py`
- `app/blueprints/inventory/routes.py`
- `app/services/tier_presentation/catalog.py`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/2026-02-17-split-inventory-quantity-tracking-from-batch-output-permission.md`
