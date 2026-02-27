# API Reference

## Synopsis
This document lists the JSON API and key HTML endpoints available in BatchTrack. All authenticated endpoints require a Flask-Login session cookie. CSRF tokens are required for all POST/PUT/DELETE requests.

## Glossary
- **Public endpoint**: No authentication required.
- **Authenticated endpoint**: Requires Flask-Login session.
- **Developer endpoint**: Requires `user_type = 'developer'`.
- **Drawer payload**: Structured error response the frontend can render as a fix-it modal (see `WALL_OF_DRAWERS_PROTOCOL.md`).

---

## Batch Operations

### Start Batch (canonical)
```
POST /batches/api/start-batch
```
Start a new batch from a client-provided PlanSnapshot.

**Request:**
```json
{
  "plan_snapshot": {
    "recipe_id": 12,
    "scale": 1.0,
    "batch_type": "product",
    "projected_yield": 10.0,
    "projected_yield_unit": "oz",
    "portioning": {
      "is_portioned": true,
      "portion_name": "bars",
      "portion_unit_id": 120,
      "portion_count": 20
    },
    "containers": [{ "id": 11, "quantity": 4 }],
    "ingredients_plan": [{ "inventory_item_id": 42, "quantity": 2.0, "unit": "count" }],
    "consumables_plan": [{ "inventory_item_id": 77, "quantity": 1.0, "unit": "count" }]
  }
}
```

**Response:** `{ "success": true, "message": "Batch started successfully", "batch_id": 34 }`

### Start Batch (compatibility)
```
POST /batches/start/start_batch
```
Builds a plan snapshot internally and delegates to `BatchOperationsService`.

### Finish / Fail Batch
```
POST /batches/finish-batch/<batch_id>/complete
POST /batches/finish-batch/<batch_id>/fail
```

### Batch Container Management
```
GET  /api/batches/<batch_id>/containers
POST /api/batches/<batch_id>/containers/<container_id>/adjust
DELETE /api/batches/<batch_id>/containers/<container_id>
```

### Batch Inventory Details
```
GET /batches/api/batch-inventory-summary/<batch_id>
GET /batches/api/batch-remaining-details/<batch_id>
GET /batches/api/available-ingredients/<recipe_id>
```

---

## Production Planning

### Stock Check
```
POST /production-planning/stock/check
```
**Body:** `{ "recipe_id": number, "scale_factor": number }`
**Returns:** `{ "success": boolean, "shortages": [...], "drawer_payload": {...} }`

### Plan Production
```
GET/POST /production-planning/recipe/<recipe_id>/plan
POST     /production-planning/recipe/<recipe_id>/plan/container
POST     /production-planning/recipe/<recipe_id>/auto-fill-containers
```

---

## FIFO & Inventory APIs

```
GET /api/inventory/item/<item_id>
GET /batches/api/batch-inventory-summary/<batch_id>
```

### Inventory Management (HTML + form POST)
```
POST /inventory/add
POST /inventory/adjust/<item_id>
POST /inventory/edit/<id>
POST /inventory/api/quick-create
POST /inventory/api/bulk-adjustments
POST /inventory/api/global-link/<item_id>
GET  /inventory/api/search
GET  /inventory/api/get-item/<item_id>
```

---

## Dashboard

```
GET  /api/dashboard-alerts
POST /api/dismiss-alert
```

**Response (alerts):**
```json
{
  "success": true,
  "data": [
    {
      "priority": "HIGH|MEDIUM|LOW",
      "type": "low_stock|expiring_items|active_batches|incomplete_batches",
      "title": "Alert Title",
      "message": "Alert description",
      "action_url": "/path/to/action",
      "dismissible": true
    }
  ]
}
```

---

## Unit Conversion

```
GET  /api/units             — List units (authenticated)
POST /api/unit-converter    — Convert units (authenticated)
GET  /api/unit-search       — Search units
GET  /api/public/units      — List units (public, no auth)
POST /api/public/convert-units — Convert units (public, no auth)
```

---

## Recipes

```
GET /api/recipes/prefix?name=...  — Generate label prefix
```

Recipe CRUD is HTML-based:
```
GET/POST /recipes/new
GET/POST /recipes/<recipe_id>/edit
GET      /recipes/<recipe_id>/view
POST     /recipes/<recipe_id>/delete
GET      /recipes/<recipe_id>/lineage
GET      /recipes/<recipe_id>/clone
GET/POST /recipes/<recipe_id>/variation
GET/POST /recipes/<recipe_id>/test
POST     /recipes/<recipe_id>/archive
POST     /recipes/<recipe_id>/restore
POST     /recipes/<recipe_id>/lock
POST     /recipes/<recipe_id>/unlock
POST     /recipes/<recipe_id>/publish-test
POST     /recipes/<recipe_id>/set-current
POST     /recipes/<recipe_id>/promote-to-master
POST     /recipes/<recipe_id>/unlist
POST     /recipes/ingredients/quick-add
POST     /recipes/units/quick-add
```

---

## Products

```
GET  /api/products/                         — List products
GET  /api/products/<product_id>/variants    — Product variants
GET  /api/products/<product_id>/inventory-summary
GET  /api/products/search
GET  /api/products/low-stock
POST /api/products/quick-add
GET  /api/products/sku/<sku_id>/product
```

Product HTML routes:
```
GET/POST /products/new
GET      /products/<product_id>
POST     /products/<product_id>/edit
POST     /products/<product_id>/delete
```

---

## Reservations

```
POST /reservations/api/reservations/create
POST /reservations/api/reservations/<order_id>/release
POST /reservations/api/reservations/<order_id>/confirm_sale
GET  /reservations/api/reservations/<order_id>/details
GET  /reservations/api/inventory/<item_id>/reservations
POST /reservations/api/reservations/cleanup_expired
```

---

## Drawer Actions

```
GET  /api/drawers/check
GET  /api/drawers/conversion/density-modal/<ingredient_id>
GET  /api/drawers/conversion/unit-mapping-modal
POST /api/drawers/conversion/unit-mapping-modal
GET  /api/drawers/containers/unit-mismatch-modal
GET  /api/drawers/global-link/check
GET  /api/drawers/global-link/modal
POST /api/drawers/global-link/confirm
GET  /api/drawers/inventory/quick-create-modal
GET  /api/drawers/units/quick-create-modal
GET  /api/drawers/retention/check
GET  /api/drawers/retention/modal
POST /api/drawers/retention/acknowledge
GET  /api/drawers/retention/export
POST /api/drawers/retry-operation
```

See `app/blueprints/api/drawers/` for implementation.

---

## Expiration

```
GET  /expiration/api/expiring-soon
GET  /expiration/api/expired-items
GET  /expiration/api/expiration-summary
GET  /expiration/api/summary
GET  /expiration/api/inventory-status/<inventory_item_id>
GET  /expiration/api/life-remaining/<fifo_id>
GET  /expiration/api/product-status/<product_id>
GET  /expiration/api/product-inventory/<inventory_id>/expiration
POST /expiration/api/mark-expired
POST /expiration/api/archive-expired
POST /expiration/api/calculate-expiration
```

---

## Timers

```
POST /timers/api/create-timer
GET  /timers/api/batch-timers/<batch_id>
GET  /timers/api/timer-status/<timer_id>
GET  /timers/api/timer-summary
GET  /timers/api/expired-timers
GET  /timers/api/check-expired
POST /timers/api/pause-timer/<timer_id>
POST /timers/api/resume-timer/<timer_id>
POST /timers/api/stop-timer/<timer_id>
POST /timers/api/cancel/<timer_id>
POST /timers/api/complete-expired
POST /timers/api/auto-expire-timers
```

---

## Tags

```
GET    /tag-manager/api/tags
POST   /tag-manager/api/tags
PUT    /tag-manager/api/tags/<tag_id>
DELETE /tag-manager/api/tags/<tag_id>
```

---

## Ingredients & Global Library (API)

```
GET /api/ingredients                               — Ingredient list
GET /api/ingredients/categories                     — Ingredient categories
GET /api/ingredients/global-items/search            — Search global items
GET /api/ingredients/global-items/<id>/stats        — Global item stats
GET /api/ingredients/global-library/density-options — Density reference
GET /api/ingredients/ingredient/<id>/density        — Item density
GET /api/ingredients/ingredients/search             — Search ingredients
GET /api/ingredients/ingredients/definitions/search — Search definitions
GET /api/ingredients/ingredients/definitions/<id>/forms
GET /api/ingredients/physical-forms/search
GET /api/ingredients/variations/search
POST /api/ingredients/ingredients/create-or-link
```

---

## Public APIs (no auth required)

```
GET  /api/public/units                  — Unit list
POST /api/public/convert-units          — Unit conversion
GET  /api/public/global-items/search    — Global item search
GET  /api/public/soapcalc-oils/search   — Soap calculator oil search
GET  /api/public/soapcalc-items/search  — Soap calculator item search
POST /api/public/help-bot               — Public help bot
GET  /api/public/server-time            — Server time
GET,POST /api/public/bot-trap           — Bot trap honeypot
```

### Soap Tool APIs (public)
```
POST /tools/api/soap/calculate       — Soap formula calculation
POST /tools/api/soap/recipe-payload  — Build canonical recipe JSON from tool data
POST /tools/api/soap/quality-nudge   — Quality-target oil nudging
GET  /tools/api/soap/oils-catalog    — Bulk oils catalog
POST /tools/api/feedback-notes       — Submit feedback note
POST /tools/draft                    — Save tool draft to session
```

---

## Organization Management

```
GET  /organization/dashboard
POST /organization/invite-user
POST /organization/create-role
POST /organization/add-user
POST /organization/update
POST /organization/update-settings
POST /organization/update-tier
GET  /organization/user/<user_id>
PUT  /organization/user/<user_id>
DELETE /organization/user/<user_id>
POST /organization/user/<user_id>/toggle-status
POST /organization/user/<user_id>/restore
GET  /organization/export/<report_type>
```

---

## Settings

```
GET  /settings/
GET  /settings/user-management
POST /settings/update-timezone
POST /settings/password/change
POST /settings/profile/save
POST /settings/set-backup-password
POST /settings/update-user-preference
POST /settings/update-system-setting
POST /settings/bulk-update-ingredients
POST /settings/bulk-update-containers
GET  /settings/api/user-preferences
POST /settings/api/user-preferences
GET  /settings/api/list-preferences/<scope>
POST /settings/api/list-preferences/<scope>
POST /settings/api/system-settings
```

---

## Billing

```
GET  /billing/upgrade
GET  /billing/checkout/<tier>
GET  /billing/checkout/<tier>/<billing_cycle>
GET  /billing/customer-portal
POST /billing/cancel-subscription
POST /billing/webhooks/stripe
GET  /billing/complete-signup-from-stripe
GET  /billing/complete-signup-from-whop
GET  /billing/storage
POST /billing/addons/start/<addon_key>
GET/POST /billing/downgrade/<tier>
GET/POST /billing/downgrade/<tier>/<billing_cycle>
```

---

## Auth

```
GET/POST /auth/login
GET/POST /auth/signup
GET/POST /auth/quick-signup
GET      /auth/logout
GET/POST /auth/forgot-password
GET/POST /auth/reset-password/<token>
GET/POST /auth/resend-verification
GET      /auth/verify-email/<token>
GET      /auth/oauth/google
GET      /auth/oauth/facebook
GET      /auth/oauth/facebook/callback
GET      /auth/oauth/callback
```

---

## Bulk Stock Check

```
GET/POST /bulk-stock/bulk-check
GET      /bulk-stock/bulk-check/csv
```

---

## Conversion Manager

```
GET/POST /conversion/units
GET      /conversion/convert/<amount>/<from_unit>/<to_unit>
POST     /conversion/add_mapping
POST     /conversion/validate_mapping
POST     /conversion/mappings/<mapping_id>/delete
POST     /conversion/units/<unit_id>/delete
```

---

## Error Codes

| HTTP Status | Meaning |
|-------------|---------|
| 200 | Success |
| 400 | Bad Request (validation errors) |
| 401 | Unauthorized (not logged in) |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Rate Limiting

Global default: `5000 per hour; 1000 per minute` (configurable via `RATELIMIT_DEFAULT`).
Backed by Redis in production, in-memory for development.
