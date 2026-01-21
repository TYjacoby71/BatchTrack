# BatchTrack Master Description

## Product summary
BatchTrack is a multi-tenant production and inventory management SaaS for small-batch makers. It turns inventory, recipes, and batching into a predictable, calm workflow so makers can ship reliably without spreadsheet math or constant mental conversions. The product is opinionated by design: it favors clear flows, reusable data, and gentle guidance that reduces cognitive load for non-technical users while still scaling to multi-tenant SaaS needs.

## Who it is for
BatchTrack is built for makers who run small-run, batch-based production such as soap makers, candle makers, apothecary brands, roasters, chocolatiers, and other artisan production teams. It supports solo makers all the way up to organizations with multiple locations, roles, and subscription tiers.

## Core workflow (end to end)
1. **Set up the workspace.** A user creates an organization, invites teammates, and assigns roles. Subscription tiers gate features and user limits.
2. **Build inventory from a shared library.** Inventory items are created from a curated Global Item Library or as organization-owned items. Global items lock identity fields so names, units, and densities stay consistent across recipes and batches. Inventory includes ingredients, packaging, containers, and consumables.
3. **Author recipes.** Recipes include ingredients, consumables, containers, and category-specific data. Each recipe chooses a portioning mode:
   - *Container-defined* (outputs are based on container sizes, like 8oz jars).
   - *Portioned* (outputs are counted as discrete units, like bars or pieces).
4. **Plan production with a PlanSnapshot.** Production planning scales a recipe, selects containers, and runs stock checks. The PlanSnapshot freezes ingredients, containers, and projected outputs so in-progress batches are protected from later recipe edits.
5. **Start and track a batch.** Starting a batch deducts inventory via FIFO, creates batch line items, and opens a live tracking view. Users can run timers, capture notes, add extras, and compare planned vs actual outputs.
6. **Finish, cancel, or fail.** Finishing records actuals and creates products or restocks intermediate inventory. Cancels roll back deductions; failures keep deductions and capture notes for audit and waste tracking.
7. **Products, SKUs, and reservations.** Finished batches replenish SKU inventory. Reservations can hold stock for customers, and integrations can sync with external systems.

## Key capabilities
- **Batch management** with structured flows and QR code support for traceable production.
- **FIFO inventory** with audit trails, lot tracking, and restock/deduct workflows.
- **Unit conversion** and density handling for consistent scaling and costing.
- **Cost of goods (COGS)** rollups across ingredients, packaging, and labor.
- **Expiration tracking** and alerting for perishable inventory.
- **Efficiency insights** such as containment and fill efficiency, planned vs actual yield.
- **Global Item Library** to prevent duplicates and keep data clean across organizations.
- **Public tools and drafts** that let anonymous users build recipes and convert them after signup.
- **Exports and reports** for inventory, recipes, and production records.

## Data model highlights
Core domain entities include Organization, User, Recipe, Batch, InventoryItem, Product, and GlobalItem. Recipes and batches are linked through immutable PlanSnapshots so production runs remain consistent even when recipes evolve.

## Architecture and guardrails
BatchTrack follows a strict service authority model. Each service is the single source of truth for its domain and must not be bypassed.

Authoritative services include:
- FIFO Service: inventory deduction order and lot management.
- Inventory Adjustment Service: all inventory changes and audit history.
- Unit Conversion Service: unit mappings and conversions.
- Stock Check Service: real-time availability validation.
- Expiration Service: shelf life calculations and alerts.

**Critical rule:** never bypass the service layer. All database operations for a domain must go through its authoritative service.

## Multi-tenant scoping and permissions
- All customer data is scoped by `organization_id`.
- Developer users have system-wide access and are not tied to an organization.
- Roles are collections of permissions, and permissions are checked with `has_permission(...)`.
- Subscription tiers gate features and capacity using `has_subscription_feature(...)`.

## PlanSnapshot and production integrity
The PlanSnapshot is an immutable contract that freezes the production plan at start. The UI reads planned values from the snapshot while actuals are tracked in batch records. This prevents recipe edits from affecting in-progress batches and keeps FIFO deductions consistent.

## Global item identity
Global items provide canonical identity, default units, density data, and metadata. When an InventoryItem is linked to a GlobalItem, identity fields lock to preserve consistency and analytics integrity. Organization-owned items remain editable.

## Timezone and data handling
All timestamps are stored in UTC. Display conversion happens at the presentation layer using TimezoneUtils so users see times in their preferred timezone without corrupting stored data.

## External dependencies and integrations
- **Backend**: Flask 3.x with Flask-SQLAlchemy and Alembic migrations.
- **Database**: PostgreSQL in production, SQLite for local development.
- **Caching and sessions**: Redis.
- **Billing**: Stripe webhooks and subscription management.
- **Optional integrations**: Shopify (inventory sync), Whop (planned marketplace publishing).
- **Auth**: Flask-Login with OAuth support (Google).

## Product positioning
BatchTrack is a calm workspace for makers. It reduces cognitive load by enforcing clean data, guiding production with structured steps, and removing the repetitive math of scaling, costing, and tracking. It is designed to feel gentle and opinionated rather than overwhelming.

## Prompt-ready summary (short form)
BatchTrack is a multi-tenant production and inventory management SaaS for small-batch makers (soap, candles, roasters, artisans). It provides a calm, opinionated workflow for inventory, recipes, production planning, and batch tracking, with FIFO deductions, unit conversions, COGS rollups, expiration tracking, and efficiency insights. The system is built on a service authority model where each service owns its domain (FIFO, inventory adjustments, unit conversion, stock checks, expiration). Data is scoped by organization_id, permissions are role-based, and subscription tiers gate features. Production planning creates an immutable PlanSnapshot so in-progress batches are protected from recipe edits. Global Item Library entries lock identity data to keep units, densities, and names consistent across the platform.
