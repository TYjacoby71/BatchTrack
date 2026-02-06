# App Dictionary (Glossary + Cross-links)

## Synopsis
This is the living glossary for BatchTrack. It is organized by application layers so new concepts can be placed where they belong and cross-linked to the source of truth.

## Update Standard (Agent Instructions)
- For every file touched, add or update the **Synopsis** (max 5 sentences).
- For every top-level functional unit touched in a file, add a **Purpose** block (max 5 sentences).
- If a file is updated, **cover the entire file** (all top-level units), not just the modified ones.
- Add dictionary entries for any new terms, routes, services, UI surfaces, or scripts touched.

---

## Glossary
- **Entry**: A single term definition within a layer.
- **Layer**: Application slice used to organize definitions (data, routes, services, UI, operations).
- **Top-Level Functional Unit**: A primary unit of logic in a file (route handler, service method, model, or script).
- **Route Handler**: A function decorated with a route that handles a request/response cycle.
- **Service Method**: A function or class method encapsulating business logic.

---

## 1. Data Layer
**Purpose**: Definitions for database models, schema fields, and invariants.

### Entries (placeholder)
- **RecipeGroup** → See [DATABASE_MODELS.md](DATABASE_MODELS.md)
- **OrganizationAddon** → See [ADDONS_AND_ENTITLEMENTS.md](ADDONS_AND_ENTITLEMENTS.md)
- **UserStats.tests_created** → Test recipe count used for badges (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **OrganizationStats.total_master_recipes** → Active master recipe count (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **OrganizationStats.total_variation_recipes** → Active variation count (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **OrganizationLeaderboardStats.most_testing_user_id** → Top tester for badge awarding (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **Recipe.is_current** → Current published version flag (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **BatchSequence** → Organization-year batch label counter (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **Batch.lineage_id** → Recipe lineage identifier recorded on batches (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **InventoryItem.quantity_base** → Integer base quantity for inventory (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **InventoryLot** → FIFO lot model for inventory tracking (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **InventoryLot.remaining_quantity_base** → Integer remaining quantity per lot (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **UnifiedInventoryHistory** → Inventory event log for adjustments (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **UnifiedInventoryHistory.quantity_change_base** → Integer change recorded per event (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **InventoryItem** → Stocked ingredient, container, or product (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **Product** → Parent product record for variants and SKUs (see [DATABASE_MODELS.md](DATABASE_MODELS.md))

---

## 2. Routes Layer
**Purpose**: Public and internal route definitions with intent and permissions.

### Entries (placeholder)
- **/developer/addons/** → Add-on catalog management
- **/billing/addons/start/<addon_key>** → Add-on checkout
- **/developer/integrations** → Developer integrations checklist and diagnostics (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-email** → Send test email from checklist (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-stripe** → Stripe connectivity check (see `app/blueprints/developer/views/integration_routes.py`)
- **/api/drawers/global-link/check** → Global link drawer availability (see `app/blueprints/api/drawers/drawer_actions/global_link.py`)
- **/api/drawers/global-link/modal** → Render global link modal (see `app/blueprints/api/drawers/drawer_actions/global_link.py`)
- **/api/drawers/global-link/confirm** → Link inventory to global items (see `app/blueprints/api/drawers/drawer_actions/global_link.py`)
- **/api/drawers/retention/check** → Retention drawer availability (see `app/blueprints/api/drawers/drawer_actions/retention.py`)
- **/api/drawers/retention/modal** → Render retention modal (see `app/blueprints/api/drawers/drawer_actions/retention.py`)
- **/api/drawers/retention/acknowledge** → Acknowledge retention items (see `app/blueprints/api/drawers/drawer_actions/retention.py`)
- **/api/drawers/retention/export** → Export retention at-risk items (see `app/blueprints/api/drawers/drawer_actions/retention.py`)
- **/api/fifo-details/<inventory_id>** → FIFO detail payload (see `app/blueprints/api/fifo_routes.py`)
- **/api/batch-inventory-summary/<batch_id>** → Batch FIFO summary (see `app/blueprints/api/fifo_routes.py`)
- **/expiration/api/expired-items** → Expired inventory summary (see `app/blueprints/expiration/routes.py`)
- **/expiration/api/expiring-soon** → Expiring-soon inventory summary (see `app/blueprints/expiration/routes.py`)
- **/expiration/api/summary** → Expiration summary counts (see `app/blueprints/expiration/routes.py`)
- **/expiration/api/calculate-expiration** → Expiration date calculator (see `app/blueprints/expiration/routes.py`)
- **/inventory/api/search** → Inventory typeahead search (see `app/blueprints/inventory/routes.py`)
- **/inventory/api/get-item/<item_id>** → Inventory item modal detail (see `app/blueprints/inventory/routes.py`)
- **/inventory/api/global-link/<item_id>** → Link/unlink item to global catalog (see `app/blueprints/inventory/routes.py`)
- **/inventory/api/quick-create** → Quick create inventory item (see `app/blueprints/inventory/routes.py`)
- **/inventory/** → Inventory list view (see `app/blueprints/inventory/routes.py`)
- **/inventory/set-columns** → Persist inventory column preferences (see `app/blueprints/inventory/routes.py`)
- **/inventory/view/<id>** → Inventory detail view (see `app/blueprints/inventory/routes.py`)
- **/inventory/add** → Create inventory item (see `app/blueprints/inventory/routes.py`)
- **/inventory/adjust/<id>** → Adjust inventory quantity (see `app/blueprints/inventory/routes.py`)
- **/inventory/edit/<id>** → Edit inventory metadata (see `app/blueprints/inventory/routes.py`)
- **/inventory/archive/<id>** → Archive inventory item (see `app/blueprints/inventory/routes.py`)
- **/inventory/restore/<id>** → Restore inventory item (see `app/blueprints/inventory/routes.py`)
- **/inventory/debug/<id>** → Inventory debug endpoint (see `app/blueprints/inventory/routes.py`)
- **/inventory/bulk-updates** → Bulk inventory update UI (see `app/blueprints/inventory/routes.py`)
- **/inventory/api/bulk-adjustments** → Bulk inventory adjustment API (see `app/blueprints/inventory/routes.py`)
- **/products/inventory/adjust/<inventory_item_id>** → Product SKU inventory adjust (see `app/blueprints/products/product_inventory_routes.py`)
- **/sku/<inventory_item_id>** → SKU detail view (see `app/blueprints/products/sku.py`)
- **/sku/<inventory_item_id>/edit** → SKU edit (see `app/blueprints/products/sku.py`)
- **/sku/merge/select** → SKU merge selection (see `app/blueprints/products/sku.py`)
- **/sku/merge/configure** → SKU merge configuration (see `app/blueprints/products/sku.py`)
- **/sku/merge/execute** → SKU merge execution (see `app/blueprints/products/sku.py`)
- **/api/sku/<sku_id>/merge_preview** → SKU merge preview API (see `app/blueprints/products/sku.py`)

---

## 3. Services Layer
**Purpose**: Service ownership and key workflows.

### Entries (placeholder)
- **BillingService** → Tier checkout + add-on activation
- **RetentionService** → Function-key retention entitlements
- **StatisticsService** → Badge and tracker aggregation (see [STATS.md](STATS.md))
- **DomainEventDispatcher** → Sends outbox events to external webhooks (see `app/services/domain_event_dispatcher.py`)
- **Integration Registry** → Integration metadata and readiness checks (see `app/services/integrations/registry.py`)
- **LazyRedisClient** → Lazy Redis client for fork-safe sessions (see `app/utils/redis_pool.py`)
- **GlobalItemSyncService** → Sync linked inventory items to global catalog changes (see `app/services/global_item_sync_service.py`)
- **CombinedInventoryAlertService** → Unified expiration and low-stock alerts (see `app/services/combined_inventory_alerts.py`)
- **CostingEngine** → Weighted unit cost helpers (see `app/services/costing_engine.py`)
- **GlobalItemStatsService** → Global item adoption and cost rollups (see `app/services/statistics/global_item_stats.py`)
- **QuantityBase** → Base quantity conversion helpers (see `app/services/quantity_base.py`)
- **InventoryAdjustmentCore** → Central adjustment delegator (see `app/services/inventory_adjustment/_core.py`)
- **InventoryAdjustmentAdditive** → Additive adjustment handlers (see `app/services/inventory_adjustment/_additive_ops.py`)
- **InventoryAdjustmentDeductive** → Deductive adjustment handlers (see `app/services/inventory_adjustment/_deductive_ops.py`)
- **InventoryAdjustmentEdit** → Inventory metadata edits + unit changes (see `app/services/inventory_adjustment/_edit_logic.py`)
- **InventoryAdjustmentSpecial** → Recount/cost override/convert handlers (see `app/services/inventory_adjustment/_special_ops.py`)
- **InventoryAdjustmentValidation** → FIFO sync validation (see `app/services/inventory_adjustment/_validation.py`)
- **InventoryCreationLogic** → Inventory item creation + initial stock (see `app/services/inventory_adjustment/_creation_logic.py`)
- **ExpirationService** → Expiration calculations and queries (see `app/blueprints/expiration/services.py`)
- **IngredientHandler** → Stock check handler for ingredients (see `app/services/stock_check/handlers/ingredient_handler.py`)
- **Auth Login Manager** → Flask-Login user loader setup (see `app/authz.py`)
- **Extensions Registry** → Shared app extensions (see `app/extensions.py`)
- **Security Middleware** → Permission and bot checks (see `app/middleware.py`)

---

## 4. UI Layer
**Purpose**: UI/UX surfaces and critical modals/forms.

### Entries (placeholder)
- **Tier Edit Form** → Permissions + add-on selection
- **Add-on Create/Edit** → Permission/function key wiring
- **Start Batch Modal** → Master + variation selection (see [SYSTEM_INDEX.md](SYSTEM_INDEX.md))
- **Integrations Checklist UI** → Environment readiness dashboard (see `app/templates/developer/integrations.html`)
- **Global Link Drawer** → Link local items to global catalog (see `app/blueprints/api/drawers/drawer_actions/global_link.py`)
- **Retention Drawer** → Acknowledge retention deletions (see `app/blueprints/api/drawers/drawer_actions/retention.py`)
- **SKU Merge Flow** → Merge SKUs into a single inventory item (see `app/blueprints/products/sku.py`)
- **Inventory Bulk Updates** → Bulk inventory adjustment UI (see `app/blueprints/inventory/routes.py`)

---

## 5. Operations Layer
**Purpose**: CLI scripts, update flows, and maintenance commands.

### Entries (placeholder)
- **flask update-permissions** → Sync permission catalog
- **flask update-addons** → Seed add-ons + backfill entitlements
- **flask update-subscription-tiers** → Sync tier limits
- **Config Schema** → Canonical env key definitions (see `app/config_schema.py`)
- **Config Schema Parts** → Domain-specific schema modules (see `app/config_schema_parts/*.py`)
- **Env Example Generator** → Generates env templates (see `scripts/generate_env_example.py`)
- **seed_test_data** → Seed living demo dataset (see `app/seeders/test_data_seeder.py`)

---

## Contribution Rules
1. Add new terms under the layer where they belong.
2. Link to the authoritative system doc for details.
3. Keep definitions concise (1–3 sentences).
4. Use consistent naming across layers (same term, same spelling).
