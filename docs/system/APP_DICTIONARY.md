# App Dictionary (Glossary + Cross-links)

## Synopsis
This is the living glossary for BatchTrack. It is organized by application layers so new concepts can be placed where they belong and cross-linked to the source of truth.

---

## Glossary
- **Entry**: A single term definition within a layer.
- **Layer**: Application slice used to organize definitions (data, routes, services, UI, operations).

---

## 1. Data Layer
**Purpose**: Definitions for database models, schema fields, and invariants.

### Entries (placeholder)
- **RecipeGroup** → See [DATABASE_MODELS.md](DATABASE_MODELS.md)
- **OrganizationAddon** → See [ADDONS_AND_ENTITLEMENTS.md](ADDONS_AND_ENTITLEMENTS.md)
- **UserStats.tests_created** → Test recipe count used for badges (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **OrganizationStats.total_master_recipes** → Active master recipe count (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **OrganizationStats.total_variation_recipes** → Active variation count (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **OrganizationLeaderboardStats.most_testing_user_id** → Top tester for badge awarding (see [DATABASE_MODELS.md](DATABASE_MODELS.md))
- **Recipe.is_current** → Current published version flag (see [DATABASE_MODELS.md](DATABASE_MODELS.md))

---

## 2. Routes Layer
**Purpose**: Public and internal route definitions with intent and permissions.

### Entries (placeholder)
- **/developer/addons/** → Add-on catalog management
- **/billing/addons/start/<addon_key>** → Add-on checkout
- **/developer/integrations** → Developer integrations checklist and diagnostics (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-email** → Send test email from checklist (see `app/blueprints/developer/views/integration_routes.py`)
- **/integrations/test-stripe** → Stripe connectivity check (see `app/blueprints/developer/views/integration_routes.py`)

---

## 3. Services Layer
**Purpose**: Service ownership and key workflows.

### Entries (placeholder)
- **BillingService** → Tier checkout + add-on activation
- **RetentionService** → Function-key retention entitlements
- **StatisticsService** → Badge and tracker aggregation (see [STATS.md](STATS.md))
- **DomainEventDispatcher** → Sends outbox events to external webhooks (see `app/services/domain_event_dispatcher.py`)
- **Integration Registry** → Integration metadata and readiness checks (see `app/services/integrations/registry.py`)
- **LazyRedisClient** → Lazy Redis client for fork-safe sessions (see `app/utils/redis_pool.py`)

---

## 4. UI Layer
**Purpose**: UI/UX surfaces and critical modals/forms.

### Entries (placeholder)
- **Tier Edit Form** → Permissions + add-on selection
- **Add-on Create/Edit** → Permission/function key wiring
- **Start Batch Modal** → Master + variation selection (see [SYSTEM_INDEX.md](SYSTEM_INDEX.md))
- **Integrations Checklist UI** → Environment readiness dashboard (see `app/templates/developer/integrations.html`)

---

## 5. Operations Layer
**Purpose**: CLI scripts, update flows, and maintenance commands.

### Entries (placeholder)
- **flask update-permissions** → Sync permission catalog
- **flask update-addons** → Seed add-ons + backfill entitlements
- **flask update-subscription-tiers** → Sync tier limits
- **Config Schema** → Canonical env key definitions (see `app/config_schema.py`)
- **Env Example Generator** → Generates env templates (see `scripts/generate_env_example.py`)

---

## Contribution Rules
1. Add new terms under the layer where they belong.
2. Link to the authoritative system doc for details.
3. Keep definitions concise (1–3 sentences).
4. Use consistent naming across layers (same term, same spelling).
