# System Documentation Index

This directory is the curated reference library for every master document that explains how BatchTrack works. Start here to understand the architecture, domain concepts, operational runbooks, and developer workflows.

## Architecture & Core Services

- **[ARCHITECTURE.md](ARCHITECTURE.md)** – System architecture, service patterns, data flow
- **[SERVICES.md](SERVICES.md)** – Service responsibilities and interaction rules
- **[DATABASE_MODELS.md](DATABASE_MODELS.md)** – Database schema and model relationships
- **[PLAN_SNAPSHOT.md](PLAN_SNAPSHOT.md)** – Immutable production planning contract and lifecycle

## Developer Workflow & Operations

- **[DEVELOPMENT_GUIDE.md](DEVELOPMENT_GUIDE.md)** – How to build and extend features safely
- **[deploy_migration_guide.md](deploy_migration_guide.md)** – Production deployment and migration checklist
- **[WALL_OF_DRAWERS_PROTOCOL.md](WALL_OF_DRAWERS_PROTOCOL.md)** – Error handling UX pattern for recoverable issues

## APIs, Integrations, and External Interfaces

- **[API_REFERENCE.md](API_REFERENCE.md)** – REST endpoints, contracts, and usage notes
- **[PUBLIC_TOOLS.md](PUBLIC_TOOLS.md)** – External utilities and integrations shipped with the platform
- **[EXPORTS.md](EXPORTS.md)** – File export architecture, formats, and delivery flows

## Product Programs & Feature Toggles

- **[FREE_TIER.md](FREE_TIER.md)** – Subscription tier allowances and gating rules
- **[TRACKING_PLAN.md](TRACKING_PLAN.md)** – Analytics instrumentation map and event taxonomy
- **[CURRENTLY_STUBBED.md](CURRENTLY_STUBBED.md)** – Feature stubs with implementation status
- **[DEPRECATED_FEATURES.md](DEPRECATED_FEATURES.md)** – Functionality scheduled for sunset and migration notes

## Inventory & Manufacturing Systems

- **[GLOBAL_ITEM_LIBRARY.md](GLOBAL_ITEM_LIBRARY.md)** – Global item curation system
- **[COMMUNITY_SCOUT.md](COMMUNITY_SCOUT.md)** – Community-sourced inventory discovery, batching, and review workflows
- **[GLOBAL_ITEM_JSON_STRUCTURE.md](GLOBAL_ITEM_JSON_STRUCTURE.md)** – JSON structure specifications
- **[CONTAINERS_CURATION.md](CONTAINERS_CURATION.md)** – Container management system
- **[CONTAINER_NAMING.md](CONTAINER_NAMING.md)** – Container naming conventions
- **[INVENTORY_EVENTS_TERMINOLOGY.md](INVENTORY_EVENTS_TERMINOLOGY.md)** – Inventory event terminology and lifecycle

## Time & Permissions

- **[TIMEZONE_SYSTEM.md](TIMEZONE_SYSTEM.md)** – Complete timezone handling guide
- **[STORAGE_VS_DISPLAY.md](STORAGE_VS_DISPLAY.md)** – DateTime storage vs display best practices
- **[USERS_AND_PERMISSIONS.md](USERS_AND_PERMISSIONS.md)** – User management and permission system

---

**All system documentation describes the current state of the platform.**  
**For change history, see [../changelog/](../changelog/)**
