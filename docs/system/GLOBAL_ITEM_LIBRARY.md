# Global Item Library (Library & Shelf Model)

## Executive Summary

The Global Item Library separates platform-managed knowledge from organization-owned stock. A read-only `GlobalItem` (the Library) provides vetted identity and expert data; an `InventoryItem` (the Shelf) represents actual, editable stock owned by an organization. This design solves bad density data, reduces friction, and preserves data integrity through a global-locked relationship.

## The Core Problem

- Bad or missing density caused incorrect weight ↔ volume conversions.
- Users faced a blank-slate, high-friction data entry burden.
- Workflows were ambiguous without contextual hints (e.g., portioned vs container-defined products).

## The Architectural Solution

- Library (`GlobalItem`): Centralized, curated data: name, `item_type`, synonyms, `default_unit`, `density`, `capacity`, perishables, contextual hints.
- Shelf (`InventoryItem`): Organization stock: quantity, cost, location, expiration, lots, etc.
- Link: Nullable `inventory_item.global_item_id` references `global_item.id` with ON DELETE SET NULL.

## Global-Locked Principle

- Creation as template: Selecting a `GlobalItem` pre-fills identity fields on the new `InventoryItem`.
- Immutability: When linked to a `GlobalItem`, identity fields are read-only for users. Users manage stock, not identity.
- Decoupling: Archiving/deleting a `GlobalItem` breaks the link (set NULL) without deleting user stock.

## Data Model

- `global_item`
  - id, name, item_type, synonyms, default_unit, density, capacity, perishables, reference_category
  - curation: platform-owned and versioned; soft-delete supported (`is_archived`)
- `inventory_item`
  - id, organization_id, name, type, quantity, unit, cost_per_unit, location, expiration, `global_item_id` (nullable), ownership ('global' | 'org')
  - relationships: FIFO history, lots, categories

## Behaviors and Validation

- Type validation: `InventoryItem.type` must match linked `GlobalItem.item_type`.
- Perishable defaults: Apply from global when not explicitly set by user.
- Categories: Suggested inventory category can be inherited from global.
- Ownership: Derived as 'global' when linked, 'org' when custom/unlinked.

## UX: The Wall of Drawers

- Smart search: One box finds curated `GlobalItem`s.
- Intelligent pre-fill: Only private fields (quantity, cost) require input.
- Proactive hints: Context (e.g., portioning) configures the correct workflow by default.
- In-context fixes: Drawer protocol resolves missing data without leaving the task.

## Developer Do / Don't

- Do link to a `GlobalItem` when creating common items; prefer library data.
- Do prevent edits to identity fields when `global_item_id` is set.
- Do keep the library curated via migrations/seeders; users should not mutate it.
- Don't duplicate library fields across services; use the link and copied fields.
- Don't cascade delete to `inventory_item`; always ON DELETE SET NULL.

## Migrations and Seeding

- `inventory_item.global_item_id` is nullable, indexed, and FK with ON DELETE SET NULL.
- Ownership backfill: set ownership to 'global' when linked, else 'org'.
- Seeding: `scripts/seed_global_items_from_density_reference.py` populates curated items from `data/density_reference.json`.

### Seeding Commands

Run inside the project root with a configured app environment:

```bash
python scripts/seed_global_items_from_density_reference.py
```

Or, if exposed via Flask CLI (example):

```bash
flask seed-global-items
```

## Integration Points

- Inventory Adjustment Creation: Applies `GlobalItem` defaults; enforces type alignment and global-locked edits.
- Density Assignment Service: Prefers library data for reference and UI suggestions.
- Developer Tools: `app/blueprints/developer/routes.py` exposes library filters and admin utilities.
- Community Scout: See [COMMUNITY_SCOUT.md](COMMUNITY_SCOUT.md) for the automated pipeline that discovers org-owned items missing from the library and feeds developers promote/link workflows.

## Future Extensions

- Category-level density hints refined by product category.
- Regional variants of `GlobalItem` via locale-scoped curation.
- Versioned `GlobalItem` releases with migration helpers.

## On the "Global Inventory List"

There is no separate "Global Inventory List" document. The function of a global list is fulfilled by the curated `GlobalItem` library plus links from `InventoryItem`. Keeping this together avoids duplication and drift; any global catalog changes belong here and in migrations/seeders.
