# BatchTrack Documentation

Welcome to the BatchTrack documentation! This directory contains all technical documentation for the system.

## 📚 Documentation Index

### Core Architecture
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture, service patterns, and design principles
- **[SERVICES.md](SERVICES.md)** - Detailed service layer specifications
- **[DATABASE_MODELS.md](DATABASE_MODELS.md)** - Database schema and model relationships

### Feature Documentation
- **[TIMEZONE_SYSTEM.md](TIMEZONE_SYSTEM.md)** - Complete timezone handling guide
- **[STORAGE_VS_DISPLAY.md](STORAGE_VS_DISPLAY.md)** - DateTime storage vs display best practices
- **[GLOBAL_ITEM_LIBRARY.md](GLOBAL_ITEM_LIBRARY.md)** - Global item curation system
- **[CONTAINERS_CURATION.md](CONTAINERS_CURATION.md)** - Container management system
- **[WALL_OF_DRAWERS_PROTOCOL.md](WALL_OF_DRAWERS_PROTOCOL.md)** - Error handling UX pattern
- **[USERS_AND_PERMISSIONS.md](USERS_AND_PERMISSIONS.md)** - Permission system guide

### Development
- **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)** - Local development setup
- **[API_REFERENCE.md](API_REFERENCE.md)** - API endpoints and usage
- **[TRACKING_PLAN.md](TRACKING_PLAN.md)** - Analytics and tracking

### Project Management
- **[changelog/](changelog/)** - ⭐ **Complete history of all fixes and improvements**
- **[CRITICAL_PRELAUNCH.md](CRITICAL_PRELAUNCH.md)** - Pre-launch requirements checklist
- **[LAUNCH_RUNBOOK.md](LAUNCH_RUNBOOK.md)** - Production launch procedures
- **[FUTURE_ROADMAP.md](FUTURE_ROADMAP.md)** - Planned features and enhancements

### QA Documentation
- **[INVENTORY_UPGRADE_QA.md](INVENTORY_UPGRADE_QA.md)** - Inventory system QA
- **[INVENTORY_COST_QA.md](INVENTORY_COST_QA.md)** - Cost tracking QA
- **[UNIT_MAPPING_QA.md](UNIT_MAPPING_QA.md)** - Unit conversion QA
- **[RETENTION_CANCELLATION_QA.md](RETENTION_CANCELLATION_QA.md)** - Retention system QA

### Reference
- **[CURRENTLY_STUBBED.md](CURRENTLY_STUBBED.md)** - Features marked for future implementation
- **[DEPRECATED_FEATURES.md](DEPRECATED_FEATURES.md)** - Deprecated/removed features
- **[EXPORTS.md](EXPORTS.md)** - Data export specifications
- **[FREE_TIER.md](FREE_TIER.md)** - Free tier limitations

## 🔍 Quick Start

### For Developers
1. Start with [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system
2. Read [DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md) for local setup
3. Review [SERVICES.md](SERVICES.md) for service layer patterns

### For Contributors
1. Check [changelog/](changelog/) for recent changes
2. Review relevant feature documentation
3. Follow patterns in [ARCHITECTURE.md](ARCHITECTURE.md)

### For Operations
1. Review [CRITICAL_PRELAUNCH.md](CRITICAL_PRELAUNCH.md) for deployment readiness
2. Check [LAUNCH_RUNBOOK.md](LAUNCH_RUNBOOK.md) for procedures
3. Monitor using guidelines in documentation

## 📋 Document Purpose Guide

| Document Type | Example | Purpose |
|---------------|---------|---------|
| **Architecture** | ARCHITECTURE.md | How the system works |
| **Guide** | TIMEZONE_SYSTEM.md | How to use a feature |
| **Best Practices** | STORAGE_VS_DISPLAY.md | Coding standards |
| **Changelog** | changelog/ | What changed and when |
| **Reference** | API_REFERENCE.md | Quick lookup |
| **QA** | INVENTORY_UPGRADE_QA.md | Test scenarios |
| **Planning** | FUTURE_ROADMAP.md | What's next |

## 🎯 Key Principles

### Service Authority
- Each service owns its domain
- Never bypass service layers
- See [ARCHITECTURE.md](ARCHITECTURE.md) for details

### Multi-Tenant Design
- All data scoped by organization
- Strict data isolation
- See [USERS_AND_PERMISSIONS.md](USERS_AND_PERMISSIONS.md)

### Timezone Handling
- **STORAGE ≠ DISPLAY**
- Always store in UTC
- Display in user's timezone
- See [STORAGE_VS_DISPLAY.md](STORAGE_VS_DISPLAY.md)

### Error Handling
- Use Drawer Protocol for user-fixable errors
- See [WALL_OF_DRAWERS_PROTOCOL.md](WALL_OF_DRAWERS_PROTOCOL.md)

## 📝 Keeping Documentation Updated

When making changes to the codebase:

1. **Architecture changes** → Update [ARCHITECTURE.md](ARCHITECTURE.md) to reflect current design
2. **Bug fixes or improvements** → Add entry to [changelog/](changelog/)
3. **New features** → Create/update feature documentation
4. **API changes** → Update [API_REFERENCE.md](API_REFERENCE.md)

## 🔗 External Links

- Main README: [../README.md](../README.md)
- Refactoring docs: [refactor/](refactor/)

---

**Last Updated**: 2025-10-28

**Maintainers**: See main README for contributor information
