# BatchTrack Operations Companion & CAQ

This document pairs **plain-language instructions** for every major system action with a **Commonly Asked Questions (CAQ)** section that links straight back to the relevant instructions. Use it as a living table of contents; each subsection references the authoritative markdown already in the repo for deeper reading.

---

## Part A — Instruction Library (How the System Works)

1. ### [Provision & Seed a New Environment](#instruction-provision)
   - **Purpose:** Stand up BatchTrack locally or in staging with all core data.
   - **Source Docs:** [`README.md`](../../README.md), [`docs/system/DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md).
   - **Key Steps:**
     1. Install Python deps (`pip install -r requirements.txt`), run `flask db upgrade`.
     2. Seed base data (`flask init-production` or modular seed commands).
     3. Export `FLASK_APP=run.py`, launch with `python run.py`.
     4. For repeatable staging builds, script the same commands plus feature-flag env vars.

2. ### [Manage Organizations, Roles, and Permissions](#instruction-org-permissions)
   - **Source Docs:** [`docs/system/USERS_AND_PERMISSIONS.md`](USERS_AND_PERMISSIONS.md).
   - **Highlights:** Developers are org-less, owners inherit all tier-allowed permissions, team members rely on roles. Always gate routes/templates with `has_permission`.
   - **Action Flow:** Owner visits `organization/dashboard` → creates or edits custom roles → invites users → assigns roles → Billing Service enforces tier caps.

3. ### [Curate the Global Item Library](#instruction-global-library)
   - **Source Docs:** [`docs/system/GLOBAL_ITEM_LIBRARY.md`](GLOBAL_ITEM_LIBRARY.md), [`docs/system/GLOBAL_ITEM_JSON_STRUCTURE.md`](GLOBAL_ITEM_JSON_STRUCTURE.md).
   - **Workflow:** Seed via `scripts/seed_global_items_from_density_reference.py`, use developer tools (`/developer/global-items`) to audit categories, rely on the new automatic metadata generator (`app/services/global_item_metadata_service.py`) for SEO descriptions.
   - **Rules:** `GlobalItem` stays read-only to customers; `InventoryItem` links via `global_item_id` with ON DELETE SET NULL.

4. ### [Create Inventory from Library Templates](#instruction-inventory)
   - **Source Docs:** [`docs/system/CONTAINERS_CURATION.md`](CONTAINERS_CURATION.md), [`docs/system/INVENTORY_EVENTS_TERMINOLOGY.md`](INVENTORY_EVENTS_TERMINOLOGY.md).
   - **Action Steps:** Search the wall-of-drawers picker, select a `GlobalItem`, let identity fields lock, then capture org-specific data (quantity, cost, lot, expiration). Adjust stock via Inventory Adjustment Service; all deductions route through FIFO.

5. ### [Author Recipes & Category Data](#instruction-recipes)
   - **Source Docs:** `app/templates/recipes/*`, [`docs/system/PLAN_SNAPSHOT.md`](PLAN_SNAPSHOT.md) (portioning guidance lives there).
   - **Process:** Define ingredients/consumables, attach containers, store category-specific JSON in `recipe.category_data`, ensure every line is linked to inventory or global items for density accuracy.

6. ### [Plan Production with PlanSnapshot](#instruction-plan)
   - **Source Docs:** [`docs/system/PLAN_SNAPSHOT.md`](PLAN_SNAPSHOT.md), [`docs/system/API_REFERENCE.md`](API_REFERENCE.md#post-batchesapistart-batch).
   - **Steps:** Call `PlanProductionService.build_plan()` to freeze the DTO, display plan preview, send the snapshot untouched to `POST /batches/api/start-batch`. Never mutate once saved.

7. ### [Start, Monitor, and Finish Batches](#instruction-batches)
   - **Source Docs:** [`docs/system/ARCHITECTURE.md`](ARCHITECTURE.md#batch-production-flow), [`docs/system/SERVICES.md`](SERVICES.md#1-fifo-service).
   - **Lifecycle:** Start batch (deductions + FIFO), track progress via `batch.plan_snapshot` vs actual rows, finish to record final yield, spawn products, and close timers/reservations.

8. ### [Restock, Deduct, and Audit Inventory](#instruction-adjustments)
   - **Source Docs:** [`docs/system/SERVICES.md`](SERVICES.md#2-inventory-adjustment-service), [`docs/system/WALL_OF_DRAWERS_PROTOCOL.md`](WALL_OF_DRAWERS_PROTOCOL.md).
   - **Actions:** Use `adjust_inventory`, `restock_inventory`, `record_spoilage` helpers; always include reasons and supplier/cost. Drawer payloads surface when density/mappings are missing.

9. ### [Track Expiration, Alerts, and Reservations](#instruction-alerts)
   - **Source Docs:** [`docs/system/SERVICES.md`](SERVICES.md#5-expiration-service), [`docs/system/ARCHITECTURE.md`](ARCHITECTURE.md#monitoring--observability).
   - **Flow:** Expiration Service computes shelf-life, Dashboard Alert Service prioritizes issues, Reservation Service blocks SKUs for orders, Combined Inventory Alert Service unifies them on the dashboard.

10. ### [Manage Products, SKUs, and Outputs](#instruction-products)
    - **Source Docs:** `app/services/product_service.py`, `app/services/reservation_service.py`.
    - **Steps:** When finishing batches, push outputs through Product Service to create/update SKUs, optionally create reservations, sync costing with FIFO data.

11. ### [Use Public Tools, Drafts, and Exports](#instruction-tools)
    - **Source Docs:** [`docs/system/PUBLIC_TOOLS.md`](PUBLIC_TOOLS.md), [`docs/system/EXPORTS.md`](EXPORTS.md).
    - **Flow:** `/tools` serves calculators → `/tools/draft` stores session payload → `/recipes/new` reads draft after auth → `/exports/...` renders HTML/CSV/PDF (both recipe and tool contexts). Public typeahead hits `/api/public/global-items/search`.

12. ### [Integrate via APIs & Webhooks](#instruction-api)
    - **Source Docs:** [`docs/system/API_REFERENCE.md`](API_REFERENCE.md).
    - **Highlights:** Authenticated routes follow Flask-Login session, developer endpoints allow org impersonation, drawer endpoints help frontends collect missing data, public APIs limited to units + global-item search + unit conversion.

13. ### [Billing, Tiers, and Feature Flags](#instruction-billing)
    - **Source Docs:** [`docs/system/FREE_TIER.md`](FREE_TIER.md), `app/services/billing_service.py`, database-backed feature flags.
    - **Steps:** Stripe webhook updates Billing Snapshot → Billing Service gates routes → `has_subscription_feature` hides/show UI; developer flags toggle experiments in the database.

14. ### [Deployments, Migrations, and Monitoring](#instruction-devops)
    - **Source Docs:** [`docs/system/deploy_migration_guide.md`](deploy_migration_guide.md), [`docs/system/DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md#database-changes), [`docs/system/ARCHITECTURE.md`](ARCHITECTURE.md#monitoring--observability).
    - **Checklist:** Create Alembic migration per schema change, run migrations with org-safe order, monitor logs (`app/middleware.py` adds security headers/logging), keep `docs/changelog` updated post-release.

15. ### [Configure Account Email Security Modes](#instruction-auth-email)
    - **Source Docs:** `app/config.py`, `app/services/email_service.py`, `app/blueprints/auth/password_routes.py`, `app/blueprints/auth/verification_routes.py`.
    - **Steps:** Choose `AUTH_EMAIL_VERIFICATION_MODE` (`off`, `prompt`, `required`), set `AUTH_EMAIL_REQUIRE_PROVIDER=true` to enable provider-aware fallback, then turn on `AUTH_PASSWORD_RESET_ENABLED` when mailbox delivery is live.
    - **Operational Rule:** If provider credentials are missing and provider-required fallback is enabled, account email verification and reset-email flows relax automatically to preserve legacy login/signup behavior.

> **Wireframe Note:** Each subsection is intentionally concise. Future agents can extend them with screenshots, drawer IDs, or SOP checklists without changing anchors.

---

## Part B — Commonly Asked Questions (CAQ)

Each CAQ links back to the instruction that resolves it.

### Access & Environment
- **How do I bootstrap a fresh workspace or reset my database?** → [Provision & Seed a New Environment](#instruction-provision)
- **Why can’t my developer account access customer data?** → [Manage Organizations, Roles, and Permissions](#instruction-org-permissions)
- **Can I run signup/login without an email provider configured yet?** → [Configure Account Email Security Modes](#instruction-auth-email)

### Inventory & Global Library
- **Where do the densities and defaults come from for new inventory?** → [Curate the Global Item Library](#instruction-global-library)
- **How do I keep inventory identity locked once it’s tied to a global item?** → [Create Inventory from Library Templates](#instruction-inventory)
- **Can I bulk-update metadata for new items?** → [Curate the Global Item Library](#instruction-global-library) (see metadata automation)

### Recipes, Planning, and Batches
- **What protects an in-progress batch from later recipe edits?** → [Plan Production with PlanSnapshot](#instruction-plan)
- **How do I scale recipes and start batches without double-deducting?** → [Start, Monitor, and Finish Batches](#instruction-batches)
- **Where do portioning and container selections live?** → [Plan Production with PlanSnapshot](#instruction-plan)

### Inventory Control & Alerts
- **What’s the proper way to restock, spoil, or adjust lots?** → [Restock, Deduct, and Audit Inventory](#instruction-adjustments)
- **How are expiration warnings surfaced on the dashboard?** → [Track Expiration, Alerts, and Reservations](#instruction-alerts)
- **Can I reserve finished goods for customers before fulfillment?** → [Manage Products, SKUs, and Outputs](#instruction-products)

### Public Surface & Integrations
- **How do anonymous users prefill recipes before signing up?** → [Use Public Tools, Drafts, and Exports](#instruction-tools)
- **Which APIs are available without authentication?** → [Integrate via APIs & Webhooks](#instruction-api)
- **How do I share INCI or label exports with vendors?** → [Use Public Tools, Drafts, and Exports](#instruction-tools)

### Billing & Operations
- **What limits the number of active users per org?** → [Billing, Tiers, and Feature Flags](#instruction-billing)
- **How do I roll out schema changes safely?** → [Deployments, Migrations, and Monitoring](#instruction-devops)
- **Where should I log launch changes or regressions?** → [Deployments, Migrations, and Monitoring](#instruction-devops) (see `docs/changelog`)

> Need another answer? Add the question here, reference the closest instruction anchor, and (if necessary) expand the instruction subsection with more detail.
