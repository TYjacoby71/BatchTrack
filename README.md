# BatchTrack

**Multi-tenant production and inventory management for small-batch makers**

BatchTrack helps soap makers, candle makers, and other artisans track recipes, manage batches, and maintain FIFO inventory while scaling from single-user to multi-tenant SaaS.

## 🚀 Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
flask db upgrade

# Seed initial data
python seed_consolidated_permissions.py
python -c "from app.seeders.unit_seeder import seed_units; seed_units()"
python -c "from app.seeders.ingredient_category_seeder import seed_categories; seed_categories()"

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

- **[Architecture Guide](docs/ARCHITECTURE.md)** - Service relationships and data flow
- **[Services Documentation](docs/SERVICES.md)** - Detailed service specifications
- **[User & Permission System](docs/USERS_AND_PERMISSIONS.md)** - Complete user management guide
- **[Database Models](docs/DATABASE_MODELS.md)** - Model relationships and migrations
- **[Development Guide](docs/DEVELOPMENT_GUIDE.md)** - How to add features safely
- **[API Reference](docs/API_REFERENCE.md)** - Endpoint documentation

## 🔒 Development Guardrails

1. **NEVER bypass services** - All inventory changes must go through proper services
2. **ALWAYS scope by organization** - Filter by `organization_id` unless you're a developer  
3. **NO hardcoded permissions** - Use `has_permission(user, permission_name)`
4. **Follow service authority** - Each service owns its domain completely
5. **Reference FIFO lots consistently** - Use `fifo_code` (never just ID)
6. **Update docs when adding services** - Maintain documentation accuracy

## 🐛 Current Issues

See [docs/FIX_LIST.md](docs/FIX_LIST.md) for known issues and [docs/QA_CHECKLIST.md](docs/QA_CHECKLIST.md) for testing requirements.

## 🔮 Future Features

See [docs/FUTURE_FEATURES.md](docs/FUTURE_FEATURES.md) for planned enhancements.

---

**⚠️ Important:** This README provides overview only. For development work, always reference the detailed documentation in `/docs` to maintain system integrity.