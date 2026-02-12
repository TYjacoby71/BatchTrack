# App Dictionary (Glossary + Cross-links)

## Synopsis
This is the living glossary for BatchTrack. It is organized by application layers so new concepts can be placed where they belong and cross-linked to the source of truth.

## Update Standard (Agent Instructions)
- Treat this block as the canonical instruction source for PR documentation checklist items related to Synopsis/Glossary, functional headers, and dictionary updates.
- For every file touched, add or update the **Synopsis** (max 5 sentences).
- For every top-level functional unit touched in a file, add a header block with **Purpose**, **Inputs**, and **Outputs** (max 5 sentences per field).
- If a file is updated, **cover the entire file** (all top-level units), not just the modified ones.
- Add dictionary entries for any new terms, routes, services, UI surfaces, or scripts touched.
- Use entry schema: `- **Term** → Description (see \`path/or/doc\`)`.
- Enforce one-entry rule: each term appears once in the layer entries (no duplicates).
- When files move or routes change, update dictionary path/location links in the same PR.
- Run `python3 scripts/validate_pr_documentation.py` before push.

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
- **RecipeLineage.event_type = PROMOTE_TEST** → Audit event logged when a test is promoted (see `app/services/recipe_service/_versioning.py`)
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
- **/tools** → Maker Tools index for public calculators (see `app/templates/tools/index.html`)
- **/tools/soap** → Soap Formulator public tool (see `app/templates/tools/soaps/index.html`)
- **/tools/api/soap/calculate** → Public soap calculator endpoint that returns structured lye/water outputs from the tool-scoped service package (see `app/routes/tools_routes.py`)
- **/pricing** → Public sales page for Hobbyist/Enthusiast/Fanatic with lifetime-first launch offers and tier comparison (see `app/routes/pricing_routes.py` and `app/templates/pages/public/pricing.html`)
- **/lp/hormozi** → Public A/B landing variant with results-first offer framing for makers (see `app/routes/landing_routes.py` and `app/templates/pages/public/landing_hormozi.html`)
- **/lp/robbins** → Public A/B landing variant with transformation-first calm workflow framing for makers (see `app/routes/landing_routes.py` and `app/templates/pages/public/landing_robbins.html`)
- **/branding/full-logo.svg, /branding/full-logo-header.svg, and /branding/app-tile.svg** → Public brand asset routes that serve attached logo SVGs, including a cropped header-ready full logo variant and the square app tile for favicon links (see `app/__init__.py`, `app/templates/components/shared/public_marketing_header.html`, `app/templates/layout.html`, and `app/templates/homepage.html`)
- **/recipes/<recipe_id>/view** → Recipe detail view with lineage navigation (see `app/blueprints/recipes/views/manage_routes.py`)
- **/recipes/<recipe_id>/lineage** → Lineage tree and history view (see `app/blueprints/recipes/views/lineage_routes.py`)
- **/recipes/<recipe_id>/variation** → Create a variation from a master (see `app/blueprints/recipes/views/create_routes.py`)
- **/recipes/<recipe_id>/test** → Create a test version for a master/variation (see `app/blueprints/recipes/views/create_routes.py`)
- **/developer/addons/** → Add-on catalog management
- **/billing/addons/start/<addon_key>** → Add-on checkout
- **/billing/upgrade** → Recoverable billing remediation page for `payment_failed`/`past_due` organizations (see `app/blueprints/billing/routes.py` and `app/services/billing_access_policy_service.py`)
- **/auth/login (inactive org lockout)** → Login denies customer access when organization status is hard-locked (`suspended`/`canceled`/inactive) and instructs users to contact support (see `app/blueprints/auth/login_routes.py`)
- **/api/recipes/prefix** → Generate a unique label prefix for recipe names (see `app/blueprints/api/routes.py`)
- **/developer/integrations** → Developer integrations checklist and diagnostics (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-email** → Send test email from checklist (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-stripe** → Stripe connectivity check (see `app/blueprints/developer/views/integration_routes.py`)
- **/auth/forgot-password** → Password reset request endpoint that issues one-time reset tokens when enabled (see `app/blueprints/auth/password_routes.py`)
- **/auth/reset-password/<token>** → Password reset completion endpoint for token-backed credential changes (see `app/blueprints/auth/password_routes.py`)
- **/auth/verify-email/<token>** → Email verification endpoint for mailbox ownership confirmation (see `app/blueprints/auth/verification_routes.py`)
- **/auth/resend-verification** → Verification resend endpoint for unverified accounts (see `app/blueprints/auth/verification_routes.py`)
- **/developer/api/user/hard-delete** → Developer-only endpoint to permanently remove a non-developer user after foreign-key cleanup (see `app/blueprints/developer/views/user_routes.py`)
- **/developer/organizations/<org_id>/delete** → Developer-only endpoint for scoped organization hard-delete with legacy marketplace archival safeguards (see `app/blueprints/developer/views/organization_routes.py`)
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
- **/recipes/<recipe_id>/notes** → Add a timestamped recipe note (see `app/blueprints/recipes/views/manage_routes.py`)
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
- **BillingService** → Tier checkout, add-on activation, and Stripe subscription cancellation primitives used by billing flows and destructive account cleanup (see `app/services/billing_service.py`)
- **BillingAccessPolicyService** → Canonical billing-access policy evaluator that returns `allow`, `require_upgrade`, or `hard_lock` decisions for auth flows (see `app/services/billing_access_policy_service.py`)
- **BillingAccessDecision** → Structured decision payload containing action + reason + message for billing gates (see `app/services/billing_access_policy_service.py`)
- **RetentionService** → Function-key retention entitlements
- **StatisticsService** → Badge and tracker aggregation (see [STATS.md](STATS.md))
- **Public Pricing Context Builder** → Aggregates tier pricing, lifetime launch availability, and comparison rows for the `/pricing` sales page (see `app/services/public_pricing_page_service.py`).
- **LineageService.generate_label_prefix** → Unique label prefix generation (see `app/services/lineage_service.py`)
- **LineageService.generate_lineage_id** → Lineage identifier with variation index + version (see `app/services/lineage_service.py`)
- **LineageService.format_label_prefix** → Version-aware label prefix display helper (see `app/services/lineage_service.py`)
- **RecipeVersioning.promote_test_to_current** → Promote a test and log lineage event (see `app/services/recipe_service/_versioning.py`)
- **RecipeFormParsing** → Form submission parsing and validation (see `app/blueprints/recipes/form_parsing.py`)
- **RecipeFormPrefill** → Prefill helpers for recipe forms (see `app/blueprints/recipes/form_prefill.py`)
- **RecipeFormTemplates** → Cached form payloads + rendering helpers (see `app/blueprints/recipes/form_templates.py`)
- **RecipeFormVariations** → Variation template construction helpers (see `app/blueprints/recipes/form_variations.py`)
- **DomainEventDispatcher** → Sends outbox events to external webhooks (see `app/services/domain_event_dispatcher.py`)
- **Integration Registry** → Integration metadata and readiness checks (see `app/services/integrations/registry.py`)
- **Developer Deletion Utils** → Shared archive/detach/fk-cleanup helpers for hard-delete workflows (see `app/services/developer/deletion_utils.py`)
- **OrganizationService.delete_organization** → Scoped organization hard-delete pipeline with marketplace JSON archival and cross-org link detachment (see `app/services/developer/organization_service.py`)
- **UserService.hard_delete_user** → Permanent non-developer user deletion with FK-safe cleanup (see `app/services/developer/user_service.py`)
- **EmailService.get_verification_mode** → Resolves effective verification mode (off/prompt/required) with provider-aware fallback (see `app/services/email_service.py`)
- **EmailService.password_reset_enabled** → Determines whether forgot/reset token flows are active for the current environment (see `app/services/email_service.py`)
- **LazyRedisClient** → Lazy Redis client for fork-safe sessions (see `app/utils/redis_pool.py`)
- **GlobalItemSyncService** → Sync linked inventory items to global catalog changes (see `app/services/global_item_sync_service.py`)
- **CombinedInventoryAlertService** → Unified expiration and low-stock alerts (see `app/services/combined_inventory_alerts.py`)
- **SKU Activity Gate** → Suppresses SKU low/out-of-stock alerts until inventory activity exists (see `app/services/combined_inventory_alerts.py`)
- **SoapToolCalculatorService Package** → Tool-scoped calculator package exporting canonical soap lye/water computations and typed request/result contracts (see `app/services/tools/__init__.py`, `app/services/tools/soap_calculator/__init__.py`, `app/services/tools/soap_calculator/service.py`, and `app/services/tools/soap_calculator/types.py`)
- **SoapToolComputationService Package** → Soap tool orchestration package that compiles lye/water, additives, quality report data, and formula sheet exports into one canonical compute response (see `app/services/tools/soap_tool/__init__.py`, `app/services/tools/soap_tool/_core.py`, `app/services/tools/soap_tool/_lye_water.py`, `app/services/tools/soap_tool/_additives.py`, `app/services/tools/soap_tool/_fatty_acids.py`, `app/services/tools/soap_tool/_quality_report.py`, `app/services/tools/soap_tool/_sheet.py`, and `app/services/tools/soap_tool/types.py`)
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
- **Security Middleware** → Request-layer enforcer for permission/bot checks and billing decision application (redirect/logout/JSON behavior) using service-provided policy decisions (see `app/middleware.py`)

---

## 4. UI Layer
**Purpose**: UI/UX surfaces and critical modals/forms.

### Entries (placeholder)
- **BT_STORAGE (Client Scope Prefix)** → Front-end storage key prefix scoped by user + org to avoid tenant bleed (see `app/templates/layout.html`)
- **System Theme Token (`data-theme='system'`)** → Explicit client-side mode that follows OS color-scheme only when the user intentionally selects System in appearance settings (see `app/templates/layout.html`, `app/templates/settings/components/appearance_tab.html`, and `app/static/css/theme.css`).
- **Tier Edit Form** → Permissions + add-on selection
- **Add-on Create/Edit** → Permission/function key wiring
- **Maker Tools Index** → Public tool hub listing live + coming maker tools (see `app/templates/tools/index.html`)
- **Maker Tools Neutral Card Styling** → Tools index cards/tiles aligned to core app surface and border tokens, replacing per-category rainbow accents (see `app/templates/tools/index.html`).
- **Public Pricing Comparison Page** → Dedicated maker-first pricing destination with lifetime launch cards, monthly/yearly plan cards, and column-style feature checks (see `app/templates/pages/public/pricing.html`)
- **Signup Tier Heading Guidance** → Legacy instructional copy beneath the signup pricing-tier heading was removed to keep tier selection concise and reduce duplicated guidance text (see `app/templates/pages/auth/signup.html`)
- **Staging Home Variants Switcher** → Public header dropdown shown only in staging to switch between classic homepage and landing A/B variants (`/lp/hormozi`, `/lp/robbins`) (see `app/templates/components/shared/public_marketing_header.html`)
- **Landing Page Variant A (Results-First)** → Public offer-led maker landing page used for A/B testing and routed to signup CTAs (see `app/templates/pages/public/landing_hormozi.html`)
- **Landing Page Variant B (Transformation-First)** → Public calm-workflow maker landing page used for A/B testing and routed to signup CTAs (see `app/templates/pages/public/landing_robbins.html`)
- **Homepage Public Footer Links** → Product/company/support/legal links mapped to concrete routes/anchors instead of placeholder targets (see `app/templates/homepage.html`)
- **Default Social Preview Image** → App-wide Open Graph/Twitter fallback image used when a page does not provide a custom `page_og_image` (see `app/static/images/og/batchtrack-default-og.svg` and `app/templates/layout.html`)
- **Tool Tiles** → Nested tool selectors within a category card (see `app/templates/tools/index.html`)
- **Soap Formulator (Public Tool)** → Batch-first soap recipe builder with quality targets (see `app/templates/tools/soaps/index.html`)
- **Edit Published Recipe Modal** → Confirmation gate for forced edits (see `app/templates/pages/recipes/view_recipe.html`)
- **Recipe Notes Panel** → Add and review timestamped recipe notes (see `app/templates/pages/recipes/view_recipe.html`)
- **Auto Label Prefix Field** → Locked prefix auto-generation on recipe forms (see `app/templates/pages/recipes/recipe_form.html`)
- **Lineage Selector (Master/Variation)** → Filtered lineage navigation (see `app/templates/pages/recipes/view_recipe.html`)
- **Lineage History Panel** → Master/variation version timelines with tests (see `app/templates/pages/recipes/recipe_lineage.html`)
- **Origin Summary (Origin/Root Recipe)** → Origin + predecessor display (see `app/templates/pages/recipes/view_recipe.html`)
- **Start Batch Modal** → Master + variation selection (see [SYSTEM_INDEX.md](SYSTEM_INDEX.md))
- **Integrations Checklist UI** → Environment readiness dashboard (see `app/templates/developer/integrations.html`)
- **Account Email Security Callout** → Integrations-page summary of configured vs effective auth-email mode and provider fallback state (see `app/templates/developer/integrations.html`)
- **Inventory Filter Persistence (Scoped)** → Per-user/org inventory filters and column preferences (see `app/templates/inventory_list.html`)
- **Bulk Inventory Drafts (Scoped)** → Per-user/org bulk update drafts stored in the browser (see `app/templates/inventory/bulk_updates.html`)
- **Drawer Cadence Throttle (Scoped)** → Per-user/org cadence window for drawer checks (see `app/static/js/drawers/drawer_cadence.js`)
- **Global Link Drawer** → Link local items to global catalog (see `app/blueprints/api/drawers/drawer_actions/global_link.py`)
- **Retention Drawer** → Acknowledge retention deletions (see `app/blueprints/api/drawers/drawer_actions/retention.py`)
- **SKU Merge Flow** → Merge SKUs into a single inventory item (see `app/blueprints/products/sku.py`)
- **Inventory Bulk Updates** → Bulk inventory adjustment UI (see `app/blueprints/inventory/routes.py`)
- **Developer User Hard Delete CTA** → Explicitly-labeled "Hard Delete User (Test Only)" modal action requiring typed confirmation before permanent deletion (see `app/templates/components/shared/user_management_modal.html`)
- **Organization Hard Delete Legacy Snapshot Notice** → Developer organization deletion modal warning that marketplace/listed recipes are archived to JSON snapshots before removal (see `app/templates/developer/organization_detail.html`)
- **Soap Formulator Runtime Modules** → Stage synchronization, autosave, and service-backed calculation orchestration for the soap tool, including additive and quality rendering modules (see `app/static/js/tools/soaps/soap_tool_core.js`, `app/static/js/tools/soaps/soap_tool_events.js`, `app/static/js/tools/soaps/soap_tool_mold.js`, `app/static/js/tools/soaps/soap_tool_oils.js`, `app/static/js/tools/soaps/soap_tool_runner.js`, `app/static/js/tools/soaps/soap_tool_storage.js`, `app/static/js/tools/soaps/soap_tool_calc.js`, `app/static/js/tools/soaps/soap_tool_additives.js`, and `app/static/js/tools/soaps/soap_tool_quality.js`)
- **Soap Formulator Stage Styling** → Soap stage card/preset visuals and lye-water setup presentation styles, including stage config template layout (see `app/static/css/tools/soaps.css` and `app/templates/tools/soaps/stages/_stage_config.html`)
- **Product Dashboard** → Product list with portfolio summary and filters (see `app/templates/pages/products/list_products.html`)
- **Product Overview** → Product detail view with variant summaries and actions (see `app/templates/pages/products/view_product.html`)
- **Variant Sizes View** → Size-level inventory and SKU actions for a variant (see `app/templates/pages/products/view_variation.html`)

---

## 5. Operations Layer
**Purpose**: CLI scripts, update flows, and maintenance commands.

### Entries (placeholder)
- **SEO Guide (Metadata Prompt)** → Maker-first metadata rules for titles/descriptions (see `docs/system/SEO_GUIDE.md`)
- **PR Documentation Guard** → Automated PR validator for synopsis/glossary, functional-unit headers, dictionary coverage, and changelog alignment (see `scripts/validate_pr_documentation.py` and `.github/workflows/documentation-guard.yml`)
- **RouteAccessConfig Public Allow-list** → Middleware public endpoint/path registry used to keep routes like `/pricing` accessible without auth (see `app/route_access.py`)
- **Landing Route Metadata Context** → Public landing routes set maker-first `page_title`, `page_description`, `canonical_url`, and OG image context consumed by `layout.html` (see `app/routes/landing_routes.py`)
- **flask update-permissions** → Sync permission catalog
- **flask update-addons** → Seed add-ons + backfill entitlements
- **flask update-subscription-tiers** → Sync tier limits
- **Config Schema** → Canonical env key definitions (see `app/config_schema.py`)
- **Config Schema Parts** → Domain-specific schema modules (see `app/config_schema_parts/*.py`)
- **Env Example Generator** → Generates env templates (see `scripts/generate_env_example.py`)
- **AUTH_EMAIL_VERIFICATION_MODE** → Auth-email policy switch (`off`, `prompt`, `required`) for signup/login posture (see `app/config.py`)
- **AUTH_EMAIL_REQUIRE_PROVIDER** → If true, disables email auth flows when provider credentials are missing (see `app/config.py`)
- **AUTH_PASSWORD_RESET_ENABLED** → Master toggle for forgot/reset password email flow (see `app/config.py`)
- **EMAIL_SMTP_ALLOW_NO_AUTH** → Allows SMTP provider checks to pass without username/password when relay policy permits (see `app/config.py`)
- **EMAIL_VERIFICATION_TOKEN_EXPIRY_HOURS** → Verification token expiry window in hours (see `app/blueprints/auth/verification_routes.py`)
- **PASSWORD_RESET_TOKEN_EXPIRY_HOURS** → Reset token expiry window in hours (see `app/blueprints/auth/password_routes.py`)
- **DELETION_ARCHIVE_DIR** → Optional app config path used to store organization hard-delete marketplace snapshot JSON files (see `app/services/developer/deletion_utils.py`)
- **seed_test_data** → Seed living demo dataset (see `app/seeders/test_data_seeder.py`)

---

## Contribution Rules
1. Add new terms under the layer where they belong.
2. Link to the authoritative system doc for details.
3. Keep definitions concise (1–3 sentences).
4. Use consistent naming across layers (same term, same spelling).
5. Keep one canonical entry per term; update the existing entry instead of duplicating.
