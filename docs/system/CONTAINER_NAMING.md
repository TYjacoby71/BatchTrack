# Container Naming Guidelines

## Synopsis
This guide defines the canonical container naming behavior used by BatchTrack inventory flows. Container names are generated from structured attributes and normalized so matching items group together. Follow this format when creating or editing container records to reduce duplicates and keep labels consistent.

## Glossary
- **Descriptor**: The text segment assembled from color/style/material/type.
- **Capacity segment**: The numeric amount and unit, such as `8 oz` or `250 ml`.
- **Canonical container name**: `<Descriptor> - <Capacity segment>` when both are available.

## Canonical Pattern (Current Implementation)
When attributes are available, names should follow:

`<Color> <Style> <Material> <Type> - <Capacity> <Unit>`

Notes:
- Missing attributes are skipped.
- Duplicate words are removed where possible (for example, avoid repeating `Glass`).
- If no descriptor is available, fallback text is used.
- If no capacity is valid, only the descriptor is used.

## Examples
Preferred:
- `Amber Boston Round Glass Bottle - 8 oz`
- `Clear Straight Sided Jar - 16 fl oz`
- `Matte Black Tin - 4 oz`
- `Container - 500 ml` (when only generic type/capacity is known)

Avoid:
- `8ozs Bottle` (non-standard unit formatting)
- `Medium Box` (no structured capacity)
- `Container A` (not meaningful for reuse/search)

## Why This Matters
- Keeps container names deterministic and searchable.
- Reduces duplicate inventory rows caused by naming drift.
- Improves downstream labels and batch/recipe container selection UX.

## Relevance Check (2026-02-17)
This guidance matches active implementation in:
- `app/services/container_name_builder.py`
- `app/services/inventory_adjustment/_creation_logic.py`
- `app/services/inventory_adjustment/_edit_logic.py`
- `app/models/inventory.py` (`InventoryItem.container_display_name` for UI display)
