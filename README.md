BatchTrack
BatchTrack is a multi-tenant production and inventory management tool built for small-batch makers. It helps manage recipes, track batches, and generate labeled products, while maintaining clean FIFO inventory tracking, product output management, and Shopify/Etsy-ready product records.

This document serves as both developer documentation and system guardrails for maintaining a consistent architecture.

✅ Core Mission & Design Principles
Audience: Small-batch makers (soap, candles, tallow, cosmetics, food) who need robust batch and inventory tracking without enterprise complexity.

Goal: Provide clean, guided workflows for non-technical makers while keeping the backend scalable for multi-tenant SaaS.

Authority & Services:

Inventory Adjustment Service = single source of truth for ALL inventory changes.

FIFO Service = authoritative order of deduction (never bypassed).

Unit Conversion Service = authoritative for all conversions.

Stock Check Service = authoritative for all real-time availability checks.

Expiration Service = authoritative for perishable tracking and alerts.

Multi-Tenancy: All data is organization-scoped. Developers live outside of organizations and have no org_id.

No Hardcoding: Permissions and roles must be dynamically assigned; subscription tiers control which roles/functions are available.

✅ Features (Current)
Batch Management

Start, cancel, and finish batches

Assign label codes with recipe prefixes

Track batch ingredients and product outputs separately

QR/Barcode integration for batch traceability

Inventory Management

FIFO-based inventory tracking (automatic batch lot deduction)

Separate ingredient vs. product inventory tracking

Expiration & freshness tracking with batch-level shelf-life inheritance

Manual restock, recount, spoilage, trash, damaged, tester tracking

Product Management

Generate labeled product SKUs with recipe prefixes

Track packaged vs bulk product outputs

Separate Product History (sales, spoilage, returns)

Ready for Shopify/Etsy integration

User & Organization System (v1 SaaS Architecture)

Multi-tenant organizations

Organization owner manages team members & roles

Subscription tier limits active users/features

✅ Getting Started (Development)
1. Install dependencies
bash
Copy
Edit
pip install -r requirements.txt
2. Initialize database
bash
Copy
Edit
flask db init
flask db migrate
flask db upgrade
3. Seed data (optional, development only)
bash
Copy
Edit
flask seed-roles-permissions
flask seed-users
4. Run the app
bash
Copy
Edit
flask run
✅ Key Services & Responsibilities
Service	Purpose	Authoritative For
FIFO Service (blueprints/fifo/services.py)	Tracks batch lots in/out	Lot order & remaining quantity
Inventory Adjustment Service (services/inventory_adjustment.py)	Applies all inventory changes	Adds history, deducts via FIFO
Unit Conversion Service (services/unit_conversion.py)	Converts between custom units	All conversions system-wide
Stock Check Service (services/stock_check.py)	Checks ingredient/product availability	Planning & batch start verification
Expiration Service (blueprints/expiration/services.py)	Calculates shelf-life, alerts, expired disposal	Expiration alerts & batch freshness
Reservation Service (services/reservation_service.py)	Reserves inventory for orders	Temporary allocation for pending sales

✅ Data & Change Types
Inventory Change Types (InventoryHistory)
Restocking
restock – Regular restock

manual_addition – Manual inventory addition

finished_batch – Inventory added from completed batch

Deductions
spoil – Spoiled inventory

trash – Trashed inventory

damaged – Damaged inventory

tester – Used for testing

batch – Deducted for batch production

Adjustments
recount – Inventory recount (overrides FIFO only for syncing)

cost_override – Adjust cost without affecting quantity

unit_conversion – Change units

refunded – Returned to inventory (cancelled batches)

Quality Control
quality_fail – Inventory failed QC

Product Change Types (ProductSKUHistory)
Restocking
produced – Product created from finished batch

Sales
sold – Product sold

shipped – Product shipped

returned – Product returned

gift – Product gifted

Loss/Waste
damaged – Damaged

spoil – Spoiled

trash – Trashed

expired – Expired

FIFO Code Prefixes
Prefix	Action
SLD	sold
SHP	shipped
SPL	spoil
TRS	trash
DMG	damaged
BCH	batch (deduction)
RCN	recount
REF	refunded
RTN	returned
CST	cost override
ADD	manual addition
TST	tester
GFT	gift
QFL	quality fail
TXN	default/unknown

✅ User & Organization System
User Types
developer – Full system access, no org_id, lives outside SaaS logic.

organization_owner – Full permissions available to their subscription tier.

team_member – Role-based permissions.

Roles & Permissions
Roles = collections of permissions

Permissions = atomic actions (inventory.adjust, batch.start, etc.)

Roles are org-scoped and assignable by the org owner

Developers can create roles & assign permissions system-wide.

Subscription Tiers
Control:

Available roles & permissions

Maximum active users (inactive users are unlimited)

Feature toggles (e.g., product sales module, advanced expiration tracking)

✅ Guardrails for Development
Never bypass services:

All inventory changes → Inventory Adjustment Service

All FIFO deductions → FIFO Service

All conversions → Unit Conversion Service

Always organization-scope data (filter by organization_id unless developer).

No hardcoded roles/permissions – use has_permission(user, permission_name).

Use the ReadMe as source of truth – all Replit prompts must follow these rules.

