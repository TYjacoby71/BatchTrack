# Global Item Library (Library & Shelf Model)

## Synopsis
The Global Item Library separates platform-curated item intelligence from organization-owned inventory rows. `GlobalItem` is the shared catalog authority; `InventoryItem` is the tenant-owned stock record that can link back to a global entry. This model keeps naming/density metadata consistent while preserving organization control over quantity, cost, and operational state.

## Glossary
- **Library item**: A platform-managed `GlobalItem` record.
- **Shelf item**: An organization-managed `InventoryItem` record.
- **Global link**: The nullable FK connection `InventoryItem.global_item_id -> GlobalItem.id`.

## Core Architecture

### Library (`GlobalItem`)
- System-level curated data model in `app/models/global_item.py`.
- Stores canonical name/type plus optional metadata (aliases, density, INCI, category tags, container metadata, formulation fields, archive state).
- Supports metadata enrichment through `app/services/global_item_metadata_service.py`.

### Shelf (`InventoryItem`)
- Tenant-scoped stock model in `app/models/inventory.py`.
- Stores operational fields (quantity, base quantity, unit, cost, expiration/perishability, category mappings, ownership).
- Optional global linkage via `global_item_id` with `ON DELETE SET NULL`.

## Linking Semantics (Current)
- `InventoryItem.global_item_id` is nullable and indexed.
- When linked, `ownership` is derived as global-sourced unless explicitly overridden by workflow logic.
- When unlinked (`global_item_id` removed), ownership is normalized back to `org`.
- Deleting/archiving global entries does not delete tenant inventory rows.

## Curation and Seeding
- Seed data lives in `app/seeders/globallist/`.
- Main seeding pipeline: `app/seeders/seed_global_inventory_library.py`.
- App CLI entrypoint: `flask seed-global-inventory` (see `app/scripts/commands/seeding.py`).

## User and Developer Surfaces

### Public/Authenticated Library Browsing
- Routes in `app/blueprints/global_library/routes.py`.
- Canonical endpoints include:
  - `/global-items`
  - `/global-items/<id>` (and slug variant)
  - `/global-items/<id>/save-to-inventory`

### Developer Curation Surfaces
- Admin workflows under `app/blueprints/developer/views/global_item_routes.py`.
- Used to manage global entries and metadata quality.

## Integration Touchpoints
- Inventory creation/edit flows consume global defaults and naming metadata.
- Search and suggestion layers use global catalog semantics for better matching.
- Statistics/services reference global item adoption and usage patterns.

## Operational Guardrails
- Prefer linking to existing global entries before creating net-new custom items.
- Keep item-type alignment consistent between `GlobalItem.item_type` and `InventoryItem.type`.
- Avoid duplicating canonical metadata across unrelated services; source from global catalog ownership boundaries.

## Relevance Check (2026-02-17)
Validated against:
- `app/models/global_item.py`
- `app/models/inventory.py`
- `app/blueprints/global_library/routes.py`
- `app/blueprints/developer/views/global_item_routes.py`
- `app/seeders/seed_global_inventory_library.py`
