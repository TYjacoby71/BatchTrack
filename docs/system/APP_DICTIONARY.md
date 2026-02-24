# App Dictionary (Glossary + Cross-links)

## Synopsis
This is the living glossary for BatchTrack. It is organized by application layers so new concepts can be placed where they belong and cross-linked to the source of truth.

## Update Standard (Agent Instructions)
- Treat this block as the canonical instruction source for PR documentation checklist items related to Synopsis/Glossary and dictionary updates.
- For newly added or materially reworked files, add or update the **Synopsis** (max 5 sentences).
- Ensure newly added Python modules include both **Synopsis** and **Glossary** in module docstrings.
- Do not expand to full-file metadata rewrites unless the PR intentionally refactors the full file.
- Add dictionary entries for any new terms, routes, services, UI surfaces, or scripts touched.
- Use entry schema: `- **Term** → Description (see \`path/or/doc\`)`.
- Enforce one-entry rule: each term appears once in the layer entries (no duplicates).
- When files move or routes change, update dictionary path/location links in the same PR.
- Use a single finalization pass: run docs guard once after implementation is complete and files are staged.
- Prefer staged-scope validation for routine finalization: `python3 scripts/validate_pr_documentation.py --staged`.
- Run `--full-link-check` only when APP_DICTIONARY links/paths changed or during release-level hardening.
- Avoid repeated repo-wide docs-guard loops unless new commits change validated files.

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
- **InventoryLot.source_type = infinite_anchor** → Special per-item anchor lot used to attach infinite-mode deduction/credit history without participating in finite FIFO quantity depletion (see `app/services/inventory_adjustment/_fifo_ops.py`)
- **UnifiedInventoryHistory** → Inventory event log for adjustments (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **UnifiedInventoryHistory.quantity_change_base** → Integer change recorded per event (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **InventoryItem** → Stocked ingredient, container, or product (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **Product** → Parent product record for variants and SKUs (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **AppSetting model** → Key/value application configuration entity used for runtime administrative settings and optional descriptions (see `app/models/app_setting.py`)

---

## 2. Routes Layer
**Purpose**: Public and internal route definitions with intent and permissions.

### Entries (placeholder)
- **/tools** → Maker Tools index for public calculators (see `app/templates/tools/index.html`)
- **/tools/soap** → Soap Formulator public tool (see `app/templates/tools/soaps/index.html`)
- **/tools/api/soap/calculate** → Public soap calculator endpoint that returns structured lye/water outputs from the tool-scoped service package (see `app/blueprints/tools/routes.py`)
- **/tools/api/soap/recipe-payload** → Public soap recipe-payload endpoint that assembles canonical soap draft JSON on the backend from calculator snapshots and tool-line context (see `app/blueprints/tools/routes.py` and `app/services/tools/soap_tool/_recipe_payload.py`)
- **/tools/api/soap/quality-nudge** → Public soap advisory endpoint that performs backend quality-target oil nudging and returns adjusted row grams for the stage-2 UI (see `app/blueprints/tools/routes.py` and `app/services/tools/soap_tool/_advisory.py`)
- **/tools/api/soap/oils-catalog** → Public bulk-oils catalog endpoint returning basics/all oils with fatty-profile fields for modal selection and import workflows (see `app/blueprints/tools/routes.py`)
- **/pricing** → Public sales page for Hobbyist/Enthusiast/Fanatic with lifetime-first launch offers and tier comparison (see `app/blueprints/pricing/routes.py` and `app/templates/pages/public/pricing.html`)
- **/lp/hormozi** → Public A/B landing variant with results-first offer framing for makers (see `app/blueprints/landing/routes.py` and `app/templates/pages/public/landing_hormozi.html`)
- **/lp/robbins** → Public A/B landing variant with transformation-first calm workflow framing for makers (see `app/blueprints/landing/routes.py` and `app/templates/pages/public/landing_robbins.html`)
- **/branding/full-logo.svg, /branding/full-logo-header.svg, and /branding/app-tile.svg** → Public brand asset routes that serve attached logo SVGs, including a cropped header-ready full logo variant and the square app tile for favicon links (see `app/__init__.py`, `app/templates/components/shared/public_marketing_header.html`, `app/templates/layout.html`, and `app/templates/homepage.html`)
- **/recipes/<recipe_id>/view** → Recipe detail view with lineage navigation (see `app/blueprints/recipes/views/manage_routes.py`)
- **/recipes/<recipe_id>/lineage** → Lineage tree and history view (see `app/blueprints/recipes/views/lineage_routes.py`)
- **/recipes/<recipe_id>/variation** → Create a variation from a master (see `app/blueprints/recipes/views/create_routes.py`)
- **/recipes/<recipe_id>/test** → Create a test version for a master/variation (see `app/blueprints/recipes/views/create_routes.py`)
- **/batches/api/start-batch** → Canonical API endpoint that performs server-side stock validation, supports force-start override notes, and starts batches from a Plan Snapshot (see `app/blueprints/batches/routes.py`)
- **/batches/start/start_batch** → Start-batch compatibility endpoint that builds a plan snapshot and delegates creation to `BatchOperationsService` (see `app/blueprints/batches/start_batch.py`)
- **/batches/finish-batch/<batch_id>/complete and /batches/finish-batch/<batch_id>/fail** → Batch completion/failure routes that delegate to service-authoritative completion logic and canonical inventory adjustment posting (see `app/blueprints/batches/finish_batch.py`)
- **Production Planning Routes** → Planning, container strategy, and stock-check endpoints used by plan-production UI flows (see `app/blueprints/production_planning/routes.py`)
- **Lineage Tree Serialization Helpers** → Utilities that format lineage node labels, nested tree payloads, and root-to-node paths for lineage UI rendering (see `app/blueprints/recipes/lineage_utils.py`)
- **/developer/addons/** → Add-on catalog management
- **/billing/addons/start/<addon_key>** → Add-on checkout
- **/billing/upgrade** → Recoverable billing remediation page for `payment_failed`/`past_due` organizations (see `app/blueprints/billing/routes.py` and `app/services/billing_access_policy_service.py`)
- **/auth/login (inactive org lockout)** → Login denies customer access when organization status is hard-locked (`suspended`/`canceled`/inactive) and instructs users to contact support (see `app/blueprints/auth/login_routes.py`)
- **OAuth + Onboarding Auth Routes** → OAuth callback/login handoff and onboarding checklist completion routing used in activation funnels (see `app/blueprints/auth/oauth_routes.py` and `app/blueprints/onboarding/routes.py`)
- **/api/recipes/prefix** → Generate a unique label prefix for recipe names (see `app/blueprints/api/routes.py`)
- **/developer/integrations** → Developer integrations checklist and diagnostics (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-email** → Send test email from checklist (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-stripe** → Stripe connectivity check (see `app/blueprints/developer/views/integration_routes.py`)
- **/auth/forgot-password** → Password reset request endpoint that issues one-time reset tokens when enabled (see `app/blueprints/auth/password_routes.py`)
- **/auth/reset-password/<token>** → Password reset completion endpoint for token-backed credential changes (see `app/blueprints/auth/password_routes.py`)
- **/auth/verify-email/<token>** → Email verification endpoint for mailbox ownership confirmation (see `app/blueprints/auth/verification_routes.py`)
- **/auth/resend-verification** → Verification resend endpoint for unverified accounts (see `app/blueprints/auth/verification_routes.py`)
- **/developer/api/profile/change-password** → Developer-only endpoint for changing the currently authenticated developer account password from the user-management page modal (see `app/blueprints/developer/views/user_routes.py`)
- **/developer/api/user/hard-delete** → Developer-only endpoint to permanently remove a non-developer user after foreign-key cleanup (see `app/blueprints/developer/views/user_routes.py`)
- **/developer/organizations/<org_id>/delete** → Developer-only endpoint for scoped organization hard-delete with legacy marketplace archival safeguards (see `app/blueprints/developer/views/organization_routes.py`)
- **Developer inventory analytics routes** → Developer-only inventory analytics dashboards and API endpoints for metrics/top-items/spoilage/data-quality/activity/catalog access (see `app/blueprints/developer/views/analytics_routes.py`)
- **/developer/api/stats** → Developer dashboard summary API endpoint for organization/user totals and tier counts (see `app/blueprints/developer/views/api_routes.py`)
- **Developer dashboard admin routes** → Developer dashboard, marketing admin, system settings, feature flags, billing integration, and waitlist-statistics views (see `app/blueprints/developer/views/dashboard_routes.py`)
- **Developer masquerade routes** → Developer support-mode organization selection, impersonation context setup, and filter/session clearing endpoints (see `app/blueprints/developer/views/masquerade_routes.py`)
- **Developer product category routes** → Product-category list/create/edit/delete management endpoints for developer administration (see `app/blueprints/developer/views/product_category_routes.py`)
- **Developer reference data routes** → Developer-maintained ingredient/reference category, density, container curation, and ingredient-attribute management endpoints (see `app/blueprints/developer/views/reference_routes.py`)
- **Export routes module** → Recipe/tool HTML and file export endpoints for INCI, labels, and production-sheet outputs (see `app/blueprints/exports/routes.py`)
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
- **/admin/organizations and /admin/organizations/<org_id>** → System-admin organization list/detail routes for internal tenant oversight (see `app/blueprints/admin/admin_routes.py`)
- **/tag-manager and /api/tags** → Authenticated tag-management UI and CRUD endpoints for organization-scoped tags (see `app/blueprints/tag_manager/routes.py`)
- **/faults/** → Permission-gated fault-log surface used for operational alert workflows (see `app/blueprints/faults/routes.py`)
- **Developer route decorator helpers** → Blueprint decorator utilities that combine login, permission, and developer-user guards for route handlers (see `app/blueprints/developer/decorators.py`)
- **/debug/validate-fifo-sync and /debug/validate-fifo-sync/<item_id>** → Internal diagnostics that validate inventory/FIFO consistency at org or item scope (see `app/blueprints/admin/debug_routes.py`)
- **Admin dev_routes relocation marker** → Legacy module documenting that developer admin routes moved into the developer blueprint namespace (see `app/blueprints/admin/dev_routes.py`)
- **Dashboard app routes** → Dashboard rendering, alert APIs, auth-check, fault-log view, and vendor-signup ingestion endpoints grouped under the app routes blueprint (see `app/blueprints/dashboard/routes.py`)
- **Developer add-on catalog routes** → Developer-only add-on list/create/edit/delete handlers for entitlement management (see `app/blueprints/developer/addons.py`)
- **Developer debug routes** → Developer diagnostics endpoints for permission and tier state inspection (see `app/blueprints/developer/debug_routes.py`)
- **Developer blueprint vendor-signup routes** → Developer dashboard vendor-signup pages and JSON ingestion endpoints registered under the developer blueprint (see `app/blueprints/developer/routes.py`)
- **Developer subscription tier management routes** → Developer tier CRUD, provider sync, and tier metadata API handlers (see `app/blueprints/developer/subscription_tiers.py`)
- **/batches/<batch_id>/containers (+ delete/adjust variants)** → Container summary/remove/adjust API surfaces that delegate operations to batch integration services (see `app/blueprints/api/container_routes.py`)
- **/api/dashboard-alerts, /api/dismiss-alert, /api/clear-dismissed-alerts** → Dashboard alert fetch + session dismissal management APIs (see `app/blueprints/api/dashboard_routes.py`)
- **containers.unit_mismatch drawer action** → Drawer endpoints for rendering and resolving recipe/container unit mismatches in production planning (see `app/blueprints/api/drawers/drawer_actions/container_unit_mismatch.py`)
- **conversion.density_modal drawer action** → Drawer endpoint for fixing missing ingredient density before retrying conversions (see `app/blueprints/api/drawers/drawer_actions/conversion_density.py`)
- **/api/drawers/retry-operation** → Generic drawer retry API that re-runs conversion operations after prerequisite fixes (see `app/blueprints/api/drawers/drawer_actions/conversion_retry.py`)
- **conversion.unit_mapping_modal drawer action** → Drawer endpoints for creating/updating custom unit mappings used by conversion flows (see `app/blueprints/api/drawers/drawer_actions/conversion_unit_mapping.py`)
- **inventory.quick_create drawer action** → Drawer endpoint that renders inline inventory quick-create UX with units and categories (see `app/blueprints/api/drawers/drawer_actions/inventory_quick_create.py`)
- **units.quick_create drawer action** → Drawer endpoint that renders custom-unit quick-create UX for interrupted workflows (see `app/blueprints/api/drawers/drawer_actions/units_quick_create.py`)
- **Ingredient API routes** → Authenticated category/density/search/create-or-link endpoints for ingredient and global-library flows (see `app/blueprints/api/ingredient_routes.py`)
- **Public utility API routes** → Unauthenticated server-time, bot-trap, global-search, soapcalc, conversion, and help-bot endpoints (see `app/blueprints/api/public.py`)
- **Reservation API routes** → Reservation create/release/convert/expire endpoints for SKU stock-hold lifecycle handling (see `app/blueprints/api/reservation_routes.py`)
- **Unit API routes** → Authenticated unit list/search/conversion endpoints for inventory tooling (see `app/blueprints/api/unit_routes.py`)
- **Auth permission matrix routes** → Permission catalog management, matrix updates, status toggles, and role helper handlers (see `app/blueprints/auth/permissions.py`)
- **Whop authentication helper** → License validation and user/org sync helper used by Whop login flows (see `app/blueprints/auth/whop_auth.py`)
- **/auth/whop-login** → Whop-backed login route that authenticates and rotates session state for licensed users (see `app/blueprints/auth/whop_routes.py`)
- **Batch add-extra route** → Endpoint for adding supplemental ingredients/containers/consumables to existing batches (see `app/blueprints/batches/add_extra.py`)
- **Batch cancellation route** → Endpoint for canceling batches with restoration summary messaging (see `app/blueprints/batches/cancel_batch.py`)
- **Bulk stock-check routes** → Bulk recipe stock evaluation and CSV shopping-list export endpoints (see `app/blueprints/bulk_stock/routes.py`)

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
- **SignupPlanCatalogService** → Builds signup-facing tier payloads with pricing displays, limits, entitlement sets, and single-tier presentation lists consumed by signup UI state (see `app/services/signup_plan_catalog_service.py`).
- **Signup Checkout Orchestration Stack** → Signup checkout state/build/fulfillment services and domain event emission for purchase funnels (see `app/services/signup_checkout_service.py`, `app/services/signup_service.py`, and `app/services/event_emitter.py`)
- **AnalyticsEventRegistry** → Canonical analytics event catalog (names, categories, required properties, and core-usage flags) used as the discoverable source of truth for product analytics emitters (see `app/services/analytics_event_registry.py`)
- **AnalyticsTrackingService** → Thin analytics relay used by feature code to emit registry-backed events and normalized signup/purchase code-usage payloads before delegating to `EventEmitter` (see `app/services/analytics_tracking_service.py`)
- **AnalyticsTiming Helper** → Reads first-landing timestamp hints and computes elapsed seconds for funnel timing enrichment (see `app/utils/analytics_timing.py`)
- **TierPresentation Package** → Declarative tier-display engine that owns feature catalogs, evaluators, formatters, helper normalization, profile selectors, and orchestration for both comparison tables and single-tier summaries (see `app/services/tier_presentation/__init__.py`, `app/services/tier_presentation/catalog.py`, `app/services/tier_presentation/core.py`, `app/services/tier_presentation/evaluators.py`, `app/services/tier_presentation/formatters.py`, `app/services/tier_presentation/helpers.py`, `app/services/tier_presentation/profiles/__init__.py`, and `app/services/tier_presentation/profiles/public_pricing.py`).
- **LineageService.generate_label_prefix** → Unique label prefix generation (see `app/services/lineage_service.py`)
- **LineageService.generate_lineage_id** → Lineage identifier with variation index + version (see `app/services/lineage_service.py`)
- **LineageService.format_label_prefix** → Version-aware label prefix display helper (see `app/services/lineage_service.py`)
- **RecipeVersioning.promote_test_to_current** → Promote a test and log lineage event (see `app/services/recipe_service/_versioning.py`)
- **RecipeCoreService** → Core create/update/delete/detail/duplicate recipe operations including group/version assignment and naming guardrails (see `app/services/recipe_service/_core.py`)
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
- **EmailService.is_configured** → Provider-readiness gate for auth-email flows; Postmark/SendGrid readiness requires both provider credentials and sender address (see `app/services/email_service.py`)
- **LazyRedisClient** → Lazy Redis client for fork-safe sessions (see `app/utils/redis_pool.py`)
- **GlobalItemSyncService** → Sync linked inventory items to global catalog changes (see `app/services/global_item_sync_service.py`)
- **CombinedInventoryAlertService** → Unified expiration and low-stock alerts (see `app/services/combined_inventory_alerts.py`)
- **SKU Activity Gate** → Suppresses SKU low/out-of-stock alerts until inventory activity exists (see `app/services/combined_inventory_alerts.py`)
- **SoapTool Lye/Water Authority** → Canonical lye/water calculation primitives and SAP normalization used across soap computations (see `app/services/tools/soap_tool/_lye_water.py`)
- **SoapToolComputationService Package** → Soap tool orchestration package that compiles lye/water, additives, quality report data, policy/config injection, backend advisory logic (blend tips + quality nudge), recipe payload assembly, bulk-oils catalog paging/caching, and formula sheet exports into one canonical compute response (see `app/services/tools/soap_tool/__init__.py`, `app/services/tools/soap_tool/_core.py`, `app/services/tools/soap_tool/_policy.py`, `app/services/tools/soap_tool/_advisory.py`, `app/services/tools/soap_tool/_recipe_payload.py`, `app/services/tools/soap_tool/_lye_water.py`, `app/services/tools/soap_tool/_catalog.py`, `app/services/tools/soap_tool/_additives.py`, `app/services/tools/soap_tool/_fatty_acids.py`, `app/services/tools/soap_tool/_quality_report.py`, `app/services/tools/soap_tool/_sheet.py`, and `app/services/tools/soap_tool/types.py`)
- **CostingEngine** → Weighted unit cost helpers (see `app/services/costing_engine.py`)
- **GlobalItemStatsService** → Global item adoption and cost rollups (see `app/services/statistics/global_item_stats.py`)
- **QuantityBase** → Base quantity conversion helpers (see `app/services/quantity_base.py`)
- **InventoryAdjustmentCore** → Central adjustment delegator (see `app/services/inventory_adjustment/_core.py`)
- **InventoryAdjustmentAdditive** → Additive adjustment handlers (see `app/services/inventory_adjustment/_additive_ops.py`)
- **InventoryAdjustmentDeductive** → Deductive adjustment handlers (see `app/services/inventory_adjustment/_deductive_ops.py`)
- **InventoryAdjustmentFifoOps** → FIFO lot operations for lot creation, deduction, cost estimation, and single-item infinite-anchor lot ownership/routing (see `app/services/inventory_adjustment/_fifo_ops.py`)
- **InventoryAdjustmentEdit** → Inventory metadata edits + unit changes (see `app/services/inventory_adjustment/_edit_logic.py`)
- **InventoryAdjustmentSpecial** → Recount/cost override/convert handlers (see `app/services/inventory_adjustment/_special_ops.py`)
- **InventoryAdjustmentValidation** → FIFO sync validation (see `app/services/inventory_adjustment/_validation.py`)
- **InventoryCreationLogic** → Inventory item creation + initial stock (see `app/services/inventory_adjustment/_creation_logic.py`)
- **InventoryTrackingPolicy** → Canonical org-tier entitlement helper that resolves whether inventory deductions should mutate on-hand quantities based strictly on `inventory.track_quantities` (see `app/services/inventory_tracking_policy.py`)
- **ExpirationService** → Expiration calculations and queries (see `app/blueprints/expiration/services.py`)
- **IngredientHandler** → Stock check handler for ingredients (see `app/services/stock_check/handlers/ingredient_handler.py`)
- **Auth Login Manager** → Flask-Login user loader setup (see `app/authz.py`)
- **Extensions Registry** → Shared app extensions (see `app/extensions.py`)
- **Security Middleware** → Request-layer enforcer for permission/bot checks and billing decision application (redirect/logout/JSON behavior) using service-provided policy decisions (see `app/middleware.py`)
- **SessionService** → Centralized session-token lifecycle helper for rotation, retrieval, and context-safe clearing behavior (see `app/services/session_service.py`)
- **JSON Store Utilities** → Atomic JSON read/write helpers with advisory file-lock support and safe default fallbacks (see `app/utils/json_store.py`)
- **Inventory Event Code Generator** → Prefix-driven event/lot code generation and validation utilities using compact base36 suffixes (see `app/utils/inventory_event_code_generator.py`)
- **Duration Humanization Utilities** → Day-count formatting helpers that convert numeric durations into friendly month/year display strings (see `app/utils/duration_utils.py`)
- **Fault Log Utility** → JSON-backed operational fault recording helper that appends timestamped structured fault entries (see `app/utils/fault_log.py`)

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
- **Soap Formulator (Public Tool)** → Batch-first soap recipe builder with quality targets, stage-based oil entry, modal-driven bulk oil selection/import, and hidden client-side DOM templates for alert/list shells so JS can render without string-built markup (see `app/templates/tools/soaps/index.html`, `app/templates/tools/soaps/_client_templates.html`, `app/templates/tools/soaps/stages/_stage_1.html`, `app/templates/tools/soaps/stages/_stage_2.html`, `app/templates/tools/soaps/stages/_stage_config.html`, `app/templates/tools/soaps/stages/_stage_4.html`, and `app/templates/tools/soaps/_modals.html`)
- **Soap Formulator Stage Row Partials** → Reusable template partials that define oil-row and fragrance-row DOM templates consumed by JS row builders without changing visual output (see `app/templates/tools/soaps/stages/partials/_oil_row_template.html`, `app/templates/tools/soaps/stages/partials/_fragrance_row_template.html`, `app/templates/tools/soaps/stages/_stage_2.html`, and `app/templates/tools/soaps/stages/_stage_5.html`)
- **Edit Published Recipe Modal** → Confirmation gate for forced edits (see `app/templates/pages/recipes/view_recipe.html`)
- **Recipe Notes Panel** → Add and review timestamped recipe notes (see `app/templates/pages/recipes/view_recipe.html`)
- **Auto Label Prefix Field** → Locked prefix auto-generation on recipe forms (see `app/templates/pages/recipes/recipe_form.html`)
- **Lineage Selector (Master/Variation)** → Filtered lineage navigation (see `app/templates/pages/recipes/view_recipe.html`)
- **Lineage History Panel** → Master/variation version timelines with tests (see `app/templates/pages/recipes/recipe_lineage.html`)
- **Origin Summary (Origin/Root Recipe)** → Origin + predecessor display (see `app/templates/pages/recipes/view_recipe.html`)
- **Recipe Group List Cards (Group-Scoped Variations)** → Recipe list card/table variation sections source rows by recipe group lineage so master-version promotions do not hide variation visibility (see `app/templates/pages/recipes/recipe_list.html` and `app/blueprints/recipes/views/manage_routes.py`)
- **Start Batch Modal** → Master + variation selection (see [SYSTEM_INDEX.md](SYSTEM_INDEX.md))
- **Batch In-Progress Timer Component** → Embedded timer table/actions for active batches, including timezone-safe display arithmetic for countdown and status badges (see `app/templates/components/batch/timer_component.html`)
- **Integrations Checklist UI** → Environment readiness dashboard (see `app/templates/developer/integrations.html`)
- **Account Email Security Callout** → Integrations-page summary of configured vs effective auth-email mode and provider fallback state (see `app/templates/developer/integrations.html`)
- **Forced Verification Modal (Legacy Unverified Accounts)** → Resend-verification UI can auto-open a forced-action modal when `forced=1` context flags are present, confirming verification-send status and next steps (see `app/templates/pages/auth/resend_verification.html`)
- **In-App Verification Reminder + Resend Actions** → Global authenticated warning alert and one-time post-login modal for older unverified accounts, both with direct resend/settings actions so users can always request a fresh verification email (see `app/templates/layout.html`, `app/templates/settings/components/profile_tab.html`, and `app/blueprints/auth/login_routes.py`)
- **Auth + Onboarding Experience Screens** → Login and onboarding templates used to capture first-session progression and setup completion timing (see `app/templates/pages/auth/login.html` and `app/templates/onboarding/welcome.html`)
- **Inventory Filter Persistence (Scoped)** → Per-user/org inventory filters and column preferences (see `app/templates/inventory_list.html`)
- **Inventory Infinite Tier UX Lock** → Inventory list create/update interactions that hide quantity inputs and bounce quantity-update actions to upgrade when org tier lacks quantity-tracking entitlement (see `app/templates/inventory_list.html`)
- **Inventory Detail Quantity Lock UX** → Inventory detail page lock behavior that greys quantity-adjustment controls, blocks recount edits, prompts upgrade, and renders effective infinite-mode summary labels under tier-forced lock state (see `app/templates/pages/inventory/view.html`, `app/templates/inventory/components/item_summary_card.html`, and `app/static/js/inventory/inventory_view.js`)
- **Inventory Lots Table (Infinite Anchor Row)** → Lot-history table rendering that highlights the special `infinite_anchor` lot with infinite badges and explanatory source text while keeping finite lots unchanged (see `app/templates/inventory/components/lots_table.html`)
- **Bulk Inventory Drafts (Scoped)** → Per-user/org bulk update drafts stored in the browser (see `app/templates/inventory/bulk_updates.html`)
- **Drawer Cadence Throttle (Scoped)** → Per-user/org cadence window for drawer checks (see `app/static/js/drawers/drawer_cadence.js`)
- **Global Link Drawer** → Link local items to global catalog (see `app/blueprints/api/drawers/drawer_actions/global_link.py`)
- **Retention Drawer** → Acknowledge retention deletions (see `app/blueprints/api/drawers/drawer_actions/retention.py`)
- **SKU Merge Flow** → Merge SKUs into a single inventory item (see `app/blueprints/products/sku.py`)
- **Timer Management Countdown Parser** → Client-side timer-list parsing/formatting guards that handle serialized timestamps safely and prevent invalid countdown output (see `app/blueprints/timers/templates/timer_list.html`)
- **Inventory Bulk Updates** → Bulk inventory adjustment UI (see `app/blueprints/inventory/routes.py`)
- **Developer User Hard Delete CTA** → Explicitly-labeled "Hard Delete User (Test Only)" modal action requiring typed confirmation before permanent deletion (see `app/templates/components/shared/user_management_modal.html`)
- **Developer Users Profile Modal** → Developer user-management page profile editor and change-password modal for the authenticated developer account (see `app/templates/developer/users.html`)
- **Organization Hard Delete Legacy Snapshot Notice** → Developer organization deletion modal warning that marketplace/listed recipes are archived to JSON snapshots before removal (see `app/templates/developer/organization_detail.html`)
- **Soap Formulator Runtime Modules** → Stage synchronization, autosave, guidance-dock updates, and service-backed calculation orchestration for the soap tool, including backend-injected policy constants/defaults, recipe-payload request context assembly, backend quality-nudge calls, template-driven alert/list shells, split bulk-oils modal modules, and modularized event orchestration for row bindings/forms/exports/mobile/init (see `app/static/js/tools/soaps/soap_tool_core.js`, `app/static/js/tools/soaps/soap_tool_constants.js`, `app/static/js/tools/soaps/soap_tool_guidance.js`, `app/static/js/tools/soaps/soap_tool_events.js`, `app/static/js/tools/soaps/soap_tool_events_rows.js`, `app/static/js/tools/soaps/soap_tool_events_forms.js`, `app/static/js/tools/soaps/soap_tool_events_exports.js`, `app/static/js/tools/soaps/soap_tool_events_mobile.js`, `app/static/js/tools/soaps/soap_tool_events_init.js`, `app/static/js/tools/soaps/soap_tool_bundle_entry.js`, `app/static/js/tools/soaps/soap_tool_mold.js`, `app/static/js/tools/soaps/soap_tool_oils.js`, `app/static/js/tools/soaps/soap_tool_bulk_oils_shared.js`, `app/static/js/tools/soaps/soap_tool_bulk_oils_render.js`, `app/static/js/tools/soaps/soap_tool_bulk_oils_api.js`, `app/static/js/tools/soaps/soap_tool_bulk_oils_modal.js`, `app/static/js/tools/soaps/soap_tool_stages.js`, `app/static/js/tools/soaps/soap_tool_runner.js`, `app/static/js/tools/soaps/soap_tool_runner_inputs.js`, `app/static/js/tools/soaps/soap_tool_runner_quota.js`, `app/static/js/tools/soaps/soap_tool_runner_service.js`, `app/static/js/tools/soaps/soap_tool_runner_render.js`, `app/static/js/tools/soaps/soap_tool_storage.js`, `app/static/js/tools/soaps/soap_tool_units.js`, `app/static/js/tools/soaps/soap_tool_calc.js`, `app/static/js/tools/soaps/soap_tool_additives.js`, `app/static/js/tools/soaps/soap_tool_quality.js`, `app/static/js/tools/soaps/soap_tool_ui.js`, and `app/static/js/tools/soaps/soap_tool_recipe_payload.js`)
- **Soap Formulator Print Finalization Guard** → Print-time mold-fill confirmation behavior that warns when final wet-batter fill is outside the configured range and optionally normalizes ingredient weights to a target mold percentage before opening print (see `app/templates/tools/soaps/_modals.html` and `app/static/js/tools/soaps/soap_tool_events_exports.js`)
- **Soap Formula Print Template** → Server-rendered print-sheet HTML template used by soap export generation so print layout remains a template concern instead of JS string assembly (see `app/templates/tools/soaps/exports/print_sheet.html` and `app/services/tools/soap_tool/_sheet.py`)
- **Soap Tool Dist Bundle Mapping (Hashed)** → Fingerprinted soap tool bundle outputs and manifest mapping used by static asset resolution so updated runtime code ships through hashed frontend assets (see `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-3ZBTVXIO.js`, `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-FCLB3YPR.js`, `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-WSLX7LVI.js`, `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-YBBGVXEH.js`, and `app/static/dist/manifest.json`)
- **Soap Formulator Stage Styling** → Soap stage card/preset visuals, lye-water setup presentation, and bulk-oils modal table layout (see `app/static/css/tools/soaps.css`, `app/templates/tools/soaps/stages/_stage_config.html`, and `app/templates/tools/soaps/stages/_stage_2.html`)
- **Product Dashboard** → Product list with portfolio summary and filters (see `app/templates/pages/products/list_products.html`)
- **Product Overview** → Product detail view with variant summaries and actions (see `app/templates/pages/products/view_product.html`)
- **Variant Sizes View** → Size-level inventory and SKU actions for a variant (see `app/templates/pages/products/view_variation.html`)
- **Product Stock Alerts Page** → Product inventory alert surface that lists out-of-stock and low-stock SKUs with breadcrumb-driven return navigation (see `app/templates/pages/products/alerts.html`)

---

## 5. Operations Layer
**Purpose**: CLI scripts, update flows, and maintenance commands.

### Entries (placeholder)
- **SEO Guide (Metadata Prompt)** → Maker-first metadata rules for titles/descriptions (see `docs/system/SEO_GUIDE.md`)
- **PR Documentation Guard** → Automated PR validator for synopsis/glossary, functional-unit headers, dictionary coverage, and changelog alignment (see `scripts/validate_pr_documentation.py` and `.github/workflows/documentation-guard.yml`)
- **RouteAccessConfig Public Allow-list** → Middleware public endpoint/path registry used to keep routes like `/pricing` accessible without auth (see `app/route_access.py`)
- **Landing Route Metadata Context** → Public landing routes set maker-first `page_title`, `page_description`, `canonical_url`, and OG image context consumed by `layout.html` (see `app/blueprints/landing/routes.py`)
- **Soap Static Asset Manifest Outputs** → Hashed soap bundle map and generated runtime bundles emitted by the scoped asset build pipeline for production cache-busting (see `app/static/dist/manifest.json`, `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-FCLB3YPR.js`, and `app/static/dist/js/tools/soaps/soap_tool_bundle_entry-WSLX7LVI.js`)
- **flask update-permissions** → Sync permission catalog
- **Consolidated Permission Catalog JSON** → Source-of-truth organization/developer permission definitions for permission syncing and audits (see `app/seeders/consolidated_permissions.json`)
- **flask update-addons** → Seed add-ons + backfill entitlements
- **flask update-subscription-tiers** → Sync tier limits
- **Subscription Tier Seed JSON** → Source-of-truth tier permission/limit metadata consumed by tier update workflows (see `app/seeders/subscription_tiers.json`)
- **SubscriptionSeeder** → Legacy/maintenance tier seeding routines used by CLI update commands (`create_*_tier`, `seed_subscription_tiers`, migrations) (see `app/seeders/subscription_seeder.py`)
- **Config Schema** → Canonical env key definitions (see `app/config_schema.py`)
- **Config Schema Parts** → Domain-specific schema modules (see `app/config_schema_parts/*.py`)
- **Env Example Generator** → Generates env templates (see `scripts/generate_env_example.py`)
- **AUTH_EMAIL_VERIFICATION_MODE** → Auth-email policy switch (`off`, `prompt`, `required`) for signup/login posture (see `app/config.py`)
- **AUTH_EMAIL_REQUIRE_PROVIDER** → If true, disables email auth flows when provider credentials are missing (see `app/config.py`)
- **AUTH_PASSWORD_RESET_ENABLED** → Master toggle for forgot/reset password email flow (see `app/config.py`)
- **EMAIL_SMTP_ALLOW_NO_AUTH** → Allows SMTP provider checks to pass without username/password when relay policy permits (see `app/config.py`)
- **GOOGLE_ANALYTICS_MEASUREMENT_ID** → Optional GA4 measurement ID that injects gtag traffic tracking in the shared layout (see `app/config.py`, `app/config_schema_parts/operations.py`, and `app/templates/layout.html`)
- **POSTHOG_PROJECT_API_KEY** → Optional PostHog project API key that enables browser analytics bootstrap in the shared layout (see `app/config.py`, `app/config_schema_parts/operations.py`, and `app/templates/layout.html`)
- **POSTHOG_HOST** → Configurable PostHog ingestion host for cloud-region or self-hosted analytics endpoints (see `app/config.py`, `app/config_schema_parts/operations.py`, and `app/templates/layout.html`)
- **POSTHOG_CAPTURE_PAGEVIEW / POSTHOG_CAPTURE_PAGELEAVE** → PostHog toggles for automatic pageview and pageleave capture in the shared layout bootstrap (see `app/config.py`, `app/config_schema_parts/operations.py`, and `app/templates/layout.html`)
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
