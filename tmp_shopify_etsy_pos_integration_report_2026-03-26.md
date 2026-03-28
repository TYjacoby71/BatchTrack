# BatchTrack POS/Marketplace Integration Report (Shopify + Etsy)

**Last edited:** 2026-03-26 (updated with owner decisions and onboarding flow detail)  
**Status:** Research + implementation blueprint (execution source of truth)

## 1) Scope captured from product direction

This report treats BatchTrack as the **source of truth** for inventory and SKU state, while supporting two-way sync with Shopify and Etsy:

- Customer connects org to Shopify/Etsy from organization dashboard.
- Add a POS/Marketplace tab with a configuration/onboarding wizard.
- Sync sale price + quantity bidirectionally where feasible.
- When BatchTrack recounts inventory, push corrected quantity to channels.
- When external sale happens, pull/push back into BatchTrack and log inventory event.
- **Order number is mandatory** and must be persisted in inventory event history.
- When batch completes and SKU is created, publish/attach SKU to connected channels.
- If SKU is removed/disconnected in BatchTrack, disable sync mapping (never hard-delete BT data).
- Disconnecting Shopify/Etsy must not delete BatchTrack products/events.

---

## 1.1 Product-owner decisions captured (2026-03-26)

These are now treated as authoritative implementation decisions unless superseded.

1. **Sale/cancel/return trigger policy must be configurable**
   - Sale application timing is org-configurable (for example, paid/fulfilled style timing).
   - Cancel/refund/return handling is configurable as automatic or manual.
2. **Price sync is bidirectional and near real-time**
   - If user saves price on Shopify/Etsy, update BatchTrack.
   - If user saves price in BatchTrack, push to Shopify/Etsy.
   - Current working rule: shared canonical price across BT/Shopify/Etsy (platform-specific promo logic remains external).
3. **Multi-location is required in V1**
   - Add organization-level marketplace location storage.
   - Import/populate locations from Shopify and allow per-SKU location mapping in BatchTrack.
4. **Etsy V1 scope is inventory + pricing hooks only**
   - Do not turn BatchTrack into a full POS/listing-media/shipping-profile management suite.
5. **No blind historical backfill by default**
   - Initial connect must ask which side seeds baseline quantities (BatchTrack or Shopify/Etsy).
6. **SKU identity priority**
   - External SKU code is primary mapping key where available.
   - If absent/incomplete, guided assignment flow must map products/variants/SKUs explicitly.
7. **Reservation model direction**
   - Evaluate handing reservations to marketplace/POS platforms where possible.
   - Inbound events can be represented in BT as direct deductions/restocks, while preserving lot-correct return behavior.
8. **Onboarding must be resumable**
   - Persist per-organization onboarding stage and progress.
   - User can leave and re-enter wizard at saved stage.

---

## 2) Current repo touch points (actual code surfaces)

## 2.1 Existing POS/inventory integration surfaces

- `app/services/pos_integration.py`
  - Already has reserve/release/confirm sale/return flows with `order_id`, `sale_price`, `source`.
  - Uses canonical inventory adjustment service.
- `app/blueprints/products/reservation_routes.py`
  - API endpoints for reservation creation, release, sale confirmation, and detail fetch.
- `app/blueprints/products/product_inventory_routes.py`
  - Existing integration endpoints:
    - `POST /products/inventory/integrations/pos/sale`
    - `POST /products/inventory/integrations/pos/return`
  - Current endpoints are login-session gated (not external webhook-ready yet).

## 2.2 Inventory event/audit storage

- `app/models/unified_inventory_history.py`
  - Already stores fields needed for commerce reconciliation:
    - `order_id`, `sale_price`, `customer`
    - `marketplace_order_id`, `marketplace_source`
    - `change_type`, `quantity_change`, `event_code`

## 2.3 Product/SKU marketplace metadata

- `app/models/product.py`
  - `Product`: `shopify_product_id`
  - `ProductSKU`: `shopify_product_id`, `shopify_variant_id`, `etsy_listing_id`, `marketplace_sync_status`, `marketplace_last_sync`
  - Good seed fields exist, but no robust connection/mapping domain model yet.

## 2.4 Eventing/analytics/outbox

- `app/models/domain_event.py`
- `app/services/event_emitter.py`
- `app/services/domain_event_dispatcher.py`
  - Outbox pattern already exists and can be reused for integration jobs/webhook relay/retries.

## 2.5 Integration registry/permissions/tier

- `app/services/integrations/registry.py`
  - Shopify/Etsy are currently marked stubbed.
- `app/seeders/consolidated_permissions.json`
  - Existing permissions: `integrations.shopify`, `integrations.marketplace`, `integrations.api_access`.
- Tier seed/catalog includes those integration permissions.

## 2.6 UI touch points for customer onboarding

- `app/templates/pages/organization/dashboard.html`
  - Has tab framework; ideal place for new POS/Marketplace tab.
- `app/static/js/organization/dashboard.js`
  - Existing dashboard AJAX framework; can host wizard UI actions.
- `app/templates/settings/index.html`
  - Secondary optional surface for per-user prefs, but org dashboard is better for org-level connectors.

---

## 3) Shopify APIs available (product, inventory, location, orders)

Primary recommendation: use **Shopify Admin GraphQL API**.

## 3.1 Core APIs for this integration

- `locations` query (discover merchant locations).
- `inventoryItem` + `InventoryLevel` (read inventory states per location).
- `inventoryAdjustQuantities` mutation (delta updates).
- `inventorySetQuantities` mutation (absolute quantity set, ideal for recount push).
- Product + variant APIs (create/update/publish SKU + price mapping).
- Order webhooks for sales ingestion (order create/paid/cancel/fulfillment domain events).

## 3.2 Sync-relevant inventory states

Shopify inventory-level quantities include states such as:

- `available`
- `committed`
- `on_hand`
- `incoming`

BatchTrack should map to an operational pair:

- BT `available_for_sale` -> Shopify `available`
- BT reservations/sales lifecycle -> event metadata + reconciliation (not direct overwrite of all states)

## 3.3 Webhook and idempotency requirements

- Use webhook signature validation (HMAC).
- Persist external event id + source for idempotency.
- Reject duplicate webhook processing safely.

References:

- https://shopify.dev/docs/api/admin-graphql/latest/queries/locations
- https://shopify.dev/docs/api/admin-graphql/latest/objects/InventoryLevel
- https://shopify.dev/docs/api/admin-graphql/latest/mutations/inventoryadjustquantities
- https://shopify.dev/docs/api/admin-graphql/latest/mutations/inventorysetquantities

---

## 4) Etsy APIs available (listing inventory + order events)

Use Etsy Open API v3 with OAuth2.

## 4.1 Core APIs for this integration

- Listing inventory read/update endpoints:
  - read listing inventory
  - update listing inventory (requires full payload replacement pattern)
- Receipt/order endpoints for order pulls and details.
- Webhooks for order lifecycle events.

## 4.2 Webhook coverage

Known Etsy webhook event topics:

- `order.paid`
- `order.shipped`
- `order.canceled`
- `order.delivered`

Use these for inbound sales/return-like lifecycle ingestion where appropriate.

## 4.3 Etsy-specific integration implications

- Inventory update often requires full listing inventory payload (not tiny partial patch).
- Need robust mapping to Etsy listing/offering structures.
- Use strict idempotency + reconciliation queues to avoid accidental listing overwrite.

References:

- https://developers.etsy.com/documentation/essentials/webhooks
- https://www.etsy.com/developers/documentation/reference/listinginventory

---

## 5) Proposed BatchTrack integration architecture (to build)

## 5.1 New domain objects (minimum)

1. **IntegrationConnection**
   - `id`, `organization_id`, `provider` (`shopify` | `etsy`)
   - `status` (`connected`, `paused`, `error`, `disconnected`)
   - OAuth tokens/encrypted secrets, expiry, scopes
   - provider account/shop metadata
2. **IntegrationLocationMap** (Shopify required)
   - maps BT organization + optional warehouse semantics to Shopify `location_id`
3. **IntegrationSkuMap**
   - `organization_id`, `provider`, `product_sku_id`
   - provider identifiers (`shopify_variant_id`, `etsy_listing_id`, etc.)
   - sync flags: `sync_enabled`, `sync_price`, `sync_quantity`
4. **IntegrationSyncEvent**
   - outbound/inbound event log, status, retries, error payloads
   - idempotency keys + external event ids
5. **IntegrationWebhookInbox**
   - raw inbound payload, signature validation status, dedupe key, processing state
6. **IntegrationOnboardingState**
   - `organization_id`, provider, stage key, stage payload, completion status, updated timestamp
   - supports resume-at-stage behavior and operator handoff

## 5.2 Service boundaries

- `app/services/integrations/shopify_service.py`
- `app/services/integrations/etsy_service.py`
- `app/services/integrations/sync_orchestrator.py`
- `app/services/integrations/webhook_verifier.py`
- `app/services/integrations/mapping_service.py`
- `app/services/integrations/onboarding_state_service.py`

All channel logic should remain out of route handlers.

## 5.3 Source-of-truth policy

- BatchTrack is authoritative for internal inventory state.
- External channels are synchronized targets.
- On reconnect after outage:
  - run reconciliation job, do not purge BT records.
- Disconnection:
  - mark connection disabled, preserve mappings/history/events.

---

## 6) End-to-end sync rules (functional contract)

## 6.1 Outbound BT -> Shopify/Etsy

1. **SKU created from batch completion**
   - If SKU has sync enabled, create/publish or map listing/variant.
2. **Recount in BatchTrack**
   - Push absolute quantity (`inventorySetQuantities` style for Shopify; Etsy full inventory update payload).
3. **Price change in BatchTrack SKU**
   - Push sale/retail price to mapped variant/listing.
4. **SKU de-selected from sync checklist**
   - Disable mapping sync flag; do not delete BT SKU/events.
5. **Location-aware sync**
   - Push to selected external location per SKU mapping (V1 multi-location support).

## 6.2 Inbound Shopify/Etsy -> BT

1. **Order paid/created webhook**
   - Resolve mapped SKU(s), decrement inventory via canonical service.
   - Persist `order_id` and provider source in `UnifiedInventoryHistory`.
2. **Cancel/refund/return events**
   - Apply reverse inventory event with reason code (auto or manual per org policy).
3. **Out-of-order events**
   - Store in inbox + replay using idempotent processor.
4. **External quantity/price save events**
   - Apply updates to BatchTrack as near real-time as provider events/API allow.
   - If webhook topic unavailable for specific field updates, use short-interval reconciliation poll.

## 6.3 Required event payload guarantees

- Must include:
  - provider (`shopify`/`etsy`)
  - provider order id
  - organization id
  - line-level SKU mapping
  - quantity
  - price
  - event timestamp

---

## 7) Customer-facing interface blueprint

## 7.1 Organization dashboard changes

Add tab on `pages/organization/dashboard.html`:

- **Tab name:** `POS & Marketplaces`
- Cards:
  - Shopify connection status + Configure button
  - Etsy connection status + Configure button
  - Last sync, pending events, failed events, reconnect action

## 7.2 Onboarding wizard

Step flow:

1. Provider selection (Shopify / Etsy)
2. OAuth connect + permissions/scopes confirmation
3. Store/shop selection (if multiple)
4. Location mapping (Shopify)
5. SKU mapping defaults
6. Sync policy:
   - quantity sync on/off
   - price sync on/off
   - sale trigger timing mode
   - cancel/refund/return mode (auto/manual)
   - pull sales events on/off
7. Dry-run test
8. Enable
9. Persist stage checkpoint after every step (resume capable)

## 7.2.1 Shopify -> BatchTrack assignment flow (guided, in-context)

When importing existing Shopify catalog into BatchTrack:

1. Show external product/listing candidate.
2. Ask user to:
   - map to existing BT product, or quick-create BT product.
3. Ask user to:
   - map to existing variant, create variant, or use Base.
4. Ask whether item is contained vs portioned.
5. If contained:
   - collect container attributes (capacity, unit, material, style/shape, optional color).
6. Assign/confirm SKU identity:
   - prefer Shopify SKU code as primary identity when present.
7. Import selected fields:
   - quantity baseline (per chosen initial-seed direction),
   - price,
   - location,
   - external identifiers.
8. Save mapping and continue item-by-item with progress state.

This should use drawer/modal-assisted contextual resolution rather than forcing users to leave onboarding.

## 7.3 Inventory page sync checklist

On SKU/inventory surfaces:

- Add per-SKU checkbox: `Sync to Shopify/Etsy`
- Optional split toggles:
  - `Sync Quantity`
  - `Sync Price`
- Bulk select actions for many SKUs.

---

## 8) Cost points and operational load points

## 8.1 Technical cost points

- OAuth token lifecycle + secure secret storage.
- Webhook verification + inbox + retry workers.
- Per-provider mapping complexity (especially Etsy full payload updates).
- Idempotency/reconciliation logic for duplicate or delayed events.
- Monitoring and alerting for sync failures.

## 8.2 Product/ops cost points

- Merchant onboarding friction (location mapping + SKU mapping).
- Support burden for mismatch cases (deleted variant/listing, renamed SKU).
- Backfill/reconciliation runtime cost for high-order-volume stores.
- Rate limit handling and backoff queues.

## 8.3 Data correctness risk points

- SKU code collisions across variants/channels.
- External edits done directly in channel UI causing drift.
- Partial failures: price pushed but quantity failed (or vice versa).
- Cross-system update collisions when both sides edit near-simultaneously.

Mitigation: split event records per operation and require clear retry state machine.

## 8.4 Conflict and cycle strategy (decision-aligned)

- Use event-driven push + webhook-driven pull as primary sync loop.
- Add periodic reconciliation as safety net for missed events.
- Use deterministic conflict policy:
  - default `last_write_wins` based on trusted event timestamp + provider event id ordering,
  - with audit visibility in sync event logs.

---

## 9) Tracking and observability requirements

## 9.1 Mandatory

- Emit domain events for:
  - integration connected/disconnected
  - webhook received/validated/failed
  - outbound sync success/failure
  - reconciliation completed
- Add provider + order id to inventory adjustment/event properties.
- Dashboard counters:
  - last successful sync
  - pending queue depth
  - failed events (24h / 7d)
  - webhook signature failures

## 9.2 Suggested event names

- `integration_connected`
- `integration_disconnected`
- `integration_sync_enqueued`
- `integration_sync_succeeded`
- `integration_sync_failed`
- `integration_webhook_received`
- `integration_webhook_rejected`
- `integration_reconciliation_completed`

---

## 10) Implementation sequence (report to follow during build)

## Phase A — Foundations (DB + service scaffolding)

- Add integration connection/mapping/event models + migration.
- Add service interfaces and provider adapters (stub methods with contracts).
- Add webhook inbox and idempotency primitives.

**Exit criteria:** Can connect test org in DB and store provider credentials safely.

## Phase B — UI onboarding + org dashboard tab

- Add `POS & Marketplaces` tab to organization dashboard.
- Add configure button and wizard shell.
- Add org-level connection status endpoints.
- Add onboarding state persistence + resume UX.

**Exit criteria:** Customer can complete connection flow in UI and see connected status.

## Phase C — SKU mapping + sync toggles

- Add inventory/SKU sync checklist.
- Persist per-SKU provider mapping and sync flags.
- Add bulk enable/disable operations.
- Add per-SKU location selector and organization location management.

**Exit criteria:** Customer can select exactly which SKUs sync.

## Phase D — Shopify first (MVP)

- Implement Shopify outbound:
  - recount -> quantity set
  - price updates
  - SKU creation/linking workflow
- Implement Shopify inbound order webhook:
  - parse order line items
  - map SKU
  - apply inventory event with order number
- Implement configurable sale/cancel/return policy behavior.
- Implement initial-seed decision screen (BT->Shopify or Shopify->BT baseline).

**Exit criteria:** Shopify sale updates BT inventory events with order id; BT recount pushes back.

## Phase E — Etsy parity

- Implement Etsy listing inventory sync with full-payload update safety.
- Implement Etsy order webhook ingestion.
- Mirror configurable policy behavior (sale/cancel/return and baseline seeding).

**Exit criteria:** Etsy order/sync loop works with same inventory event guarantees.

## Phase F — Reconciliation + hardening

- Add replay/reconcile jobs.
- Add monitoring, retries, dead-letter handling.
- Add admin diagnostics page + support tooling.

**Exit criteria:** Recoverable from disconnects, out-of-order webhooks, and partial failures.

---

## 11) Immediate first build tickets (next execution steps)

1. Add `IntegrationConnection` + `IntegrationSkuMap` + `IntegrationWebhookInbox` models/migration.
2. Add `IntegrationOnboardingState` model + resume service.
3. Add organization dashboard `POS & Marketplaces` tab + status endpoint.
4. Add Shopify OAuth callback skeleton + encrypted token persistence.
5. Add SKU sync checklist fields/API on product SKU surfaces (including location map).
6. Add webhook ingestion endpoint with signature verification + idempotency store.
7. Add org sync-policy settings:
   - sale trigger timing
   - auto/manual cancel-refund-return handling
   - initial baseline seed direction
8. Wire inventory event enrichment to always include provider + order id on external sales.

---

## 12) Non-goals (for initial implementation)

- Do not let external disconnect/remove delete BatchTrack records.
- Do not attempt one-shot “all marketplaces at once” abstraction before Shopify MVP works end-to-end.
- Do not bypass canonical inventory adjustment service for marketplace writes.

