# BatchTrack

**Multi-tenant production and inventory management for small-batch makers**

BatchTrack helps soap makers, candle makers, and other artisans track recipes, manage batches, and maintain FIFO inventory while scaling from single-user to multi-tenant SaaS.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
flask db upgrade

# Seed all essential data (recommended for new installations)
flask init-production

# OR seed components individually:
# flask seed-permissions
# flask seed-sub-tiers  
# flask seed-units
# flask seed-users

# Run the application
python run.py
```

## 🚢 Render Deployment Commands

For source-controlled, repeatable Render deploys, use:

- **Build Command:** `./scripts/render-build.sh`
- **Start Command:** `gunicorn wsgi:app`

The build script installs Python and Node dependencies, runs `flask db upgrade`, and then runs `flask build-assets`.

## 🎯 Core Mission

**For:** Small-batch makers who need robust batch tracking without enterprise complexity
**Goal:** Clean, guided workflows for non-technical users with scalable SaaS backend
**Authority:** Service-based architecture where each service has single responsibility

## 📋 Key Features

- **Batch Management**: Start, track, and finish production batches with QR codes
- **FIFO Inventory**: Automatic first-in-first-out inventory deduction
- **Multi-tenant Organizations**: Subscription-based user management
- **Recipe Scaling**: Dynamic ingredient calculations with unit conversions
- **Expiration Tracking**: Automatic shelf-life management and alerts
- **Product Management**: SKU generation and sales tracking

## 🏗️ Architecture Overview

### Service Authority (Never Bypass)
- **FIFO Service**: Authoritative for all inventory deductions
- **Inventory Adjustment Service**: Single source of truth for inventory changes
- **Unit Conversion Service**: Handles all unit conversions
- **Stock Check Service**: Real-time availability validation
- **Expiration Service**: Shelf-life calculations and alerts

### Data Scoping
- **Multi-tenant**: All data scoped by `organization_id`
- **Developer Users**: Live outside organizations, system-wide access
- **Subscription Tiers**: Control available features and user limits

## 📚 Documentation

Start with the curated system library, then drill into checklists and change history as needed.

### System Documentation (`docs/system/`)
- **[System Documentation Index](docs/system/SYSTEM_INDEX.md)** — master table of contents for every platform area
- **[App Dictionary](docs/system/APP_DICTIONARY.md)** — layered glossary with cross-links to source files

| Topic | Key Docs |
| --- | --- |
| Architecture & service authority | [ARCHITECTURE.md](docs/system/ARCHITECTURE.md), [SERVICES.md](docs/system/SERVICES.md), [DATABASE_MODELS.md](docs/system/DATABASE_MODELS.md) |
| Production planning & manufacturing | [PLAN_SNAPSHOT.md](docs/system/PLAN_SNAPSHOT.md), [GLOBAL_ITEM_LIBRARY.md](docs/system/GLOBAL_ITEM_LIBRARY.md), [CONTAINERS_CURATION.md](docs/system/CONTAINERS_CURATION.md) |
| Inventory & event terminology | [INVENTORY_EVENTS_TERMINOLOGY.md](docs/system/INVENTORY_EVENTS_TERMINOLOGY.md), [CONTAINER_NAMING.md](docs/system/CONTAINER_NAMING.md) |
| Developer workflow & operations | [DEVELOPMENT_GUIDE.md](docs/system/DEVELOPMENT_GUIDE.md), [deploy_migration_guide.md](docs/system/deploy_migration_guide.md), [OPERATIONS_AND_FAQ.md](docs/system/OPERATIONS_AND_FAQ.md) |
| APIs & external interfaces | [API_REFERENCE.md](docs/system/API_REFERENCE.md), [PUBLIC_TOOLS.md](docs/system/PUBLIC_TOOLS.md), [EXPORTS.md](docs/system/EXPORTS.md) |
| Product programs & billing | [FREE_TIER.md](docs/system/FREE_TIER.md), [TIER_FEATURE_CATALOG.md](docs/system/TIER_FEATURE_CATALOG.md), [ADDONS_AND_ENTITLEMENTS.md](docs/system/ADDONS_AND_ENTITLEMENTS.md), [BILLING.md](docs/system/BILLING.md) |
| Analytics & statistics | [TRACKING_PLAN.md](docs/system/TRACKING_PLAN.md), [STATS.md](docs/system/STATS.md) |
| Time & permissions | [TIMEZONE_SYSTEM.md](docs/system/TIMEZONE_SYSTEM.md), [STORAGE_VS_DISPLAY.md](docs/system/STORAGE_VS_DISPLAY.md), [USERS_AND_PERMISSIONS.md](docs/system/USERS_AND_PERMISSIONS.md) |
| UX patterns | [WALL_OF_DRAWERS_PROTOCOL.md](docs/system/WALL_OF_DRAWERS_PROTOCOL.md) |
| Platform status & lifecycle | [CURRENTLY_STUBBED.md](docs/system/CURRENTLY_STUBBED.md), [DEPRECATED_FEATURES.md](docs/system/DEPRECATED_FEATURES.md) |

### Operational Checklists (`docs/todo/`)
- **[Consolidated Backlog](docs/todo/CONSOLIDATED_BACKLOG.md)** — launch blockers, bugs, and feature backlog

### Change History (`docs/changelog/`)
- **[Change Log Index](docs/changelog/CHANGELOG_INDEX.md)** — full record of shipped changes with links to detailed entries

### Refactor Initiatives (`docs/refactor/`)
- Progress trackers and technical debt initiatives, starting with [00_repo_map.md](docs/refactor/00_repo_map.md)

### Marketing
- **[Marketing Workspace](app/marketing/README.md)** — Overview of site content, structure, and tooling

## 🔒 Development Guardrails

1. **NEVER bypass services** - All inventory changes must go through proper services
2. **ALWAYS scope by organization** - Filter by `organization_id` unless you're a developer  
3. **NO hardcoded permissions** - Use `has_permission(user, permission_name)`
4. **Follow service authority** - Each service owns its domain completely
5. **Reference FIFO lots consistently** - Use `fifo_code` (never just ID)
6. **Use drawers for user-fixable errors** - Return `drawer_payload` instead of hard-blocking
7. **Respect Global-Locked identity** - Do not mutate identity on items linked to `GlobalItem`
8. **Update docs when adding services** - Maintain documentation accuracy

## 🛠️ Maintenance Scripts

Run with the app environment active:

```bash
python scripts/dev_test_runner.py
python scripts/audit_route_permissions.py
python scripts/refresh_global_item_metadata.py
```

## 🐛 Current Issues

See [docs/todo/CONSOLIDATED_BACKLOG.md](docs/todo/CONSOLIDATED_BACKLOG.md) for launch blockers, bugs, and the full feature backlog.

## 🔮 Future Features

See the "Future Features & Growth" section in [docs/todo/CONSOLIDATED_BACKLOG.md](docs/todo/CONSOLIDATED_BACKLOG.md).

---
