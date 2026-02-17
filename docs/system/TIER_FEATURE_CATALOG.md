# Tier Feature Catalog and Entitlement Mapping

## Synopsis
This document defines a customer-facing feature catalog for BatchTrack and maps each feature to the underlying enforcement layer (permissions, add-ons, feature flags, and numeric limits). Use this as the source of truth when building pricing tiers, comparison tables, and upgrade copy.

## Glossary
- **Feature**: Customer-facing capability label used in pricing and onboarding copy.
- **Permission**: RBAC action key (for example, `inventory.adjust`) enforced by `require_permission(...)`.
- **Add-on entitlement**: Optional capability granted via `allowed_addons` / `included_addons` or active `OrganizationAddon`.
- **Function-key add-on**: Add-on without RBAC permission, enforced in service logic (for example, retention).
- **Feature flag**: Toggle that enables or hides a capability surface (for example, `FEATURE_GLOBAL_ITEM_LIBRARY`).
- **Limit**: Numeric cap from `SubscriptionTier` (for example, `user_limit`, `max_batchbot_requests`).

## 1. Entitlement layers (what tiers actually control)

| Layer | Authority | Example | Enforcement style |
| --- | --- | --- | --- |
| Permission | `SubscriptionTier.permissions` + role intersection | `recipes.plan_production` | Hard route/service gate |
| Add-on (permission) | `Addon.permission_name` | `ai.batchbot` | Adds/removes permission access |
| Add-on (function key) | `Addon.function_key` | `retention` | Service-level behavior switch |
| Feature flag | `FeatureFlag` / settings | `FEATURE_BULK_INVENTORY_UPDATES` | Visibility / route enablement |
| Numeric limit | `SubscriptionTier` fields | `user_limit=10` | Usage cap (if enforced in code) |

## 2. Customer-facing feature catalog

Use these labels on pricing pages and sales collateral. Keep permission keys internal.

### 2.1 Inventory and stock intelligence

| Feature label (pricing copy) | Backing gates | Current status |
| --- | --- | --- |
| Inventory workspace (view/edit/adjust stock) | `inventory.view`, `inventory.edit`, `inventory.adjust` | Live |
| FIFO lot tracking and traceability | Lot + history models, FIFO ops, inventory routes (`inventory.view`) | Live (always-on core behavior) |
| Quantity + cost tracking | Inventory fields + costing engine (`FEATURE_COST_TRACKING` always-on) | Live |
| Expiration and freshness tracking | Expiration routes/services (`inventory.view` / `inventory.adjust`) | Live |
| Inventory reservations (hold/release stock) | `inventory.reserve` + reservation/POS services | Live |
| Bulk inventory updates | `FEATURE_BULK_INVENTORY_UPDATES`, bulk routes (`inventory.edit` / `inventory.adjust`) | Wired (flagged) |
| Bulk stock check + shopping list export | `FEATURE_BULK_STOCK_CHECK`, `recipes.plan_production` | Wired (flagged) |
| Global Inventory Library (browse) | `FEATURE_GLOBAL_ITEM_LIBRARY`, public routes | Live (flagged) |
| Save global items into org inventory | Global library save route + `inventory.edit` | Live |

### 2.2 Recipes and production

| Feature label (pricing copy) | Backing gates | Current status |
| --- | --- | --- |
| Recipe management (create/edit/delete) | `recipes.view`, `recipes.create`, `recipes.edit`, `recipes.delete` | Live |
| Recipe scaling | `recipes.scale` | Live |
| Production planning and stock simulation | `recipes.plan_production` | Live |
| Recipe variations and lineage workflows | `recipes.create_variations` (also seeded add-on key `recipe_variations`) | Live |
| Batch execution (start/edit/finish/cancel) | `batches.create`, `batches.edit`, `batches.finish`, `batches.cancel`, `batches.view` | Live |
| Batch-level FIFO/freshness insight modal | FIFO APIs + freshness summaries (`batches.view`, `inventory.view`) | Live |
| Recipe sharing controls | `recipes.sharing_controls` + `FEATURE_RECIPE_MARKETPLACE_LISTINGS` | Live |
| Recipe purchase controls | `recipes.purchase_options` + `FEATURE_RECIPE_MARKETPLACE_LISTINGS` | Live |

### 2.3 Products, variants, and sales operations

| Feature label (pricing copy) | Backing gates | Current status |
| --- | --- | --- |
| Product catalog (CRUD) | `products.view`, `products.create`, `products.edit`, `products.delete` | Live |
| Product variants and SKU management | `products.manage_variants`, variant/SKU routes | Live |
| Sales tracking and depletion | `products.sales_tracking` + inventory adjustment flows | Live |
| POS reservation flow (reserve/confirm/release/return) | `inventory.reserve` + POS service | Partial (core flow works; service still contains stubs/mocks) |

### 2.4 Team and organization management

| Feature label (pricing copy) | Backing gates | Current status |
| --- | --- | --- |
| Organization dashboard and settings | `organization.view`, `organization.edit` | Live |
| Team member management | `organization.manage_users` + user-limit checks | Live |
| Role and permission management | `organization.manage_roles` (+ `FEATURE_ORG_ROLE_MANAGEMENT` for tab display) | Live |
| Billing and plan management | `organization.manage_billing` | Live |
| Audit log visibility | `organization.view_audit_logs` | Permission exists; validate route coverage before marketing heavily |

### 2.5 Marketplace, public tools, and growth surfaces

| Feature label (pricing copy) | Backing gates | Current status |
| --- | --- | --- |
| Public maker tools (soap/candle/lotion/herbal/baking) | `/tools/*` routes + `TOOLS_*` flags | Live |
| Public tools draft handoff to app | `/tools/draft` + recipe prefill flow | Live |
| Public Recipe Library | `FEATURE_RECIPE_MARKETPLACE_DISPLAY` + marketplace listing rules | Live |
| Organization marketplace pages | `recipes.marketplace_dashboard` + recipe library flags | Live |
| Public Global Item Library SEO pages | Global library public routes + feature flag | Live |

### 2.6 AI and reporting

| Feature label (pricing copy) | Backing gates | Current status |
| --- | --- | --- |
| BatchBot assistant | `ai.batchbot` + `FEATURE_BATCHBOT` | Live |
| BatchBot refill credits | Add-on `batchbot_refill_100` (`function_key=batchbot_credits`) | Live |
| Basic reporting | `reports.view` | Live |
| Export reports | `reports.export` | Live |
| Advanced/custom reporting | `reports.advanced`, `reports.custom` | Live in permission model; premium packaging decision is product-level |
| AI recipe optimization / demand forecasting / quality insights | Feature flags + AI permission family | Stub/experimental surfaces today |

### 2.7 Data lifecycle and retention

| Feature label (pricing copy) | Backing gates | Current status |
| --- | --- | --- |
| Standard retention (1 year) | Default behavior when no retention entitlement is active | Live |
| Extended retention while subscribed | Retention add-on (`function_key=retention`) included or purchased | Live |
| Retention warning + export + acknowledgement workflow | Retention drawer endpoints (`recipes.delete`) + queueing service | Live |

## 3. Limits model and enforcement status

| Tier field | Intended meaning | Enforcement status today |
| --- | --- | --- |
| `user_limit` | Active non-developer users per org | Hard enforced in invite/add/activation flows (`Organization.can_add_users`) |
| `max_recipes` | Active recipe cap | Enforced during downgrade/archive/restore workflows |
| `max_batchbot_requests` | BatchBot request cap per usage window | Hard enforced by `BatchBotUsageService` (+ refill credits) |
| `max_products` | Product cap | Stored/displayed in tier metadata; no global hard-create gate found |
| `max_batches` | Batch cap | Stored/displayed in tier metadata; no global hard-create gate found |
| `max_monthly_batches` | Monthly batch cap | Stored/displayed in tier metadata; no global hard-create gate found |
| `retention_policy` / `data_retention_days` | Data lifecycle policy | Enforced via retention service + drawer/queue flow |

## 4. Recommended tier-construction rules

These rules prevent inconsistent plans.

1. **Multi-user plans**
   - If `user_limit > 1`, include:
     - `organization.view`
     - `organization.manage_users`
     - `organization.manage_roles`
     - `organization.manage_billing`
   - Note: this is not auto-derived from `user_limit`; you must assign permissions explicitly.

2. **BatchBot-enabled plans**
   - If BatchBot is marketed as included:
     - Include `ai.batchbot`.
     - Set `max_batchbot_requests` > 0 or `-1`.
     - Optionally offer refill add-on.

3. **Marketplace seller plans**
   - For listing recipes publicly:
     - `recipes.sharing_controls`
     - `recipes.marketplace_dashboard`
     - Feature flags for marketplace surfaces must be enabled in environment.
   - For paid recipe links:
     - `recipes.purchase_options`.

4. **Global library import plans**
   - Public browsing is open, but saving to org inventory requires `inventory.edit`.

5. **Bulk operations plans**
   - Bulk stock check requires both permission (`recipes.plan_production`) and feature flag.
   - Bulk inventory updates require inventory permissions plus feature flag.

6. **Retention messaging**
   - Market this as a feature outcome:
     - "1-year retention" (default)
     - "Retention while subscribed" (retention entitlement active)
   - Avoid exposing raw internals like queue windows unless in help docs.

## 5. Pricing-table presentation guidance

For pricing pages, show **feature outcomes and limits**, not raw permission names.

Recommended row groups:

1. **Build & Run**: inventory, recipes, batches, product workflow.
2. **Control & Insight**: FIFO traceability, cost visibility, freshness, reports.
3. **Team & Governance**: seats, users/roles, billing controls.
4. **Growth Surfaces**: public tools, marketplace, global library, integrations.
5. **AI & Automation**: BatchBot access + monthly action cap.
6. **Scale Limits**: users, recipes, products, batches/month, BatchBot requests.

## 6. Known gaps to resolve before final commercial packaging

1. **Add-on permission mismatch**
   - `advanced_analytics` add-on seeds `permission_name='reports.analytics'`, but the main permission catalog uses `reports.advanced` / `reports.custom`.
   - Decide canonical key and align seed + permission catalog.

2. **Non-enforced numeric caps**
   - `max_products`, `max_batches`, `max_monthly_batches` are model-level metadata but do not appear to have universal hard gates yet.
   - If sold as strict limits, add enforcement points (create/start workflows + API paths).

3. **Integration positioning**
   - Shopify/Etsy integration flags are currently marked stubbed/partial in developer catalog.
   - Market as "roadmap/experimental" until end-to-end integration contracts are production-hard.

## 7. Practical implementation plan (recommended)

1. Keep this document as product source of truth.
2. Add a `feature_catalog` config map (code-level) that ties:
   - pricing feature label
   - required permissions
   - required feature flags
   - optional limit field
3. Generate pricing comparison rows from that map, not from raw permission labels.
4. Keep developer screens permission-first; keep public pages outcome-first.

