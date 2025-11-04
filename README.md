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

For detailed development information, see:

### System Documentation
- **[System Documentation Index](docs/system/SYSTEM_INDEX.md)** - Complete guide to all system docs
  - Architecture, Services, Database Models
  - Timezone System, User Permissions
  - Global Item Library, Drawers Protocol
  - And more...

### Development Resources
- **[Development Guide](docs/DEVELOPMENT_GUIDE.md)** - How to add features safely
- **[API Reference](docs/API_REFERENCE.md)** - Endpoint documentation
- **[Deployment & Migrations](docs/deploy_migration_guide.md)** - Runbook for production changes

### Change History
- **[Change Log Index](docs/changelog/CHANGELOG_INDEX.md)** - Complete history of all fixes and improvements

### Marketing
- **[Marketing Workspace](marketing/README.md)** - Overview of site content, structure, and tooling

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
python scripts/clear_inventory_history.py
python scripts/dev_test_runner.py
```

## 🐛 Current Issues

See [docs/todo/FIX_IMMEDIATE.md](docs/todo/FIX_IMMEDIATE.md) for the active fix list and [docs/todo/CRITICAL_PRELAUNCH.md](docs/todo/CRITICAL_PRELAUNCH.md) for launch-blocking tasks and QA gate checks.

## 🔮 Future Features

See [docs/FUTURE_ROADMAP.md](docs/FUTURE_ROADMAP.md) for planned enhancements.

---

**⚠️ Important:** This README provides overview only. For development work, always reference the detailed documentation in `/docs` to maintain system integrity.