# Inventory Events Terminology

This document defines the canonical terms used for inventory tracking.

Core entities:
- Inventory Item: The thing you stock (ingredient, container, product, etc.).
- Inventory Lot: A stored quantity that is consumable. Holds remaining quantity, unit cost, expiration, etc.
- Inventory Event: Any change to inventory. Persisted as a row in `UnifiedInventoryHistory`.

Identifiers:
- Event Code: Customer-facing identifier string for an inventory event. Stored in DB as `fifo_code`. Aliased in code as `event_code`.
- Reference Lot Id: Preferred pointer to the lot involved in the event. Stored in DB as `affected_lot_id`. Aliased in code as `reference_lot_id`.
- Legacy: `fifo_reference_id` (reference to another event). Deprecated in favor of `affected_lot_id`.

Generation:
 - Event codes are generated in `app/utils/inventory_event_code_generator.py` based on `change_type`.
- Lot-creating operations use `LOT-` prefix; finished batch events display the batch label as the event code.

Display rules:
- Used For column: Always show the batch label.
- Credited/Debited column: Always show the affected lot’s event code (LOT-...).
- Event Code column: Show the event’s event code. If finished batch without event code, display the batch label.

Change Types and prefixes:
- recount: RCN-
- sale: SLD-
- use: USE-
- spoil: SPL-
- trash: TRS-
- expired: EXP-
- damaged: DMG-
- quality_fail: QFL-
- batch consumption: BCH- (when code generated), or batch label when present
- sample: SMP-
- tester: TST-
- gift: GFT-
- returned: RTN-
- refunded: REF-
- cost_override: CST-
- fallback: EVT-

Known inconsistencies to avoid:
- “FIFO event” is legacy; use “Inventory event”.
- UI should never show prefix plus batch label together; for finished batch display only the batch label.
- Prefer `event_code` terminology in code; DB columns remain `fifo_code` for backward compatibility.

Migration guidance (future work):
- Optionally migrate DB column names from `fifo_code` -> `event_code`, `fifo_reference_id` -> `reference_event_id`.
- Replace legacy logs and help text that say “FIFO event” with “Inventory event”.
