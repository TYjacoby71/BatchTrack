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

---

## 2. Routes Layer
**Purpose**: Public and internal route definitions with intent and permissions.

### Entries (placeholder)
- **/developer/addons/** → Add-on catalog management
- **/billing/addons/start/<addon_key>** → Add-on checkout

---

## 3. Services Layer
**Purpose**: Service ownership and key workflows.

### Entries (placeholder)
- **BillingService** → Tier checkout + add-on activation
- **RetentionService** → Function-key retention entitlements

---

## 4. UI Layer
**Purpose**: UI/UX surfaces and critical modals/forms.

### Entries (placeholder)
- **Tier Edit Form** → Permissions + add-on selection
- **Add-on Create/Edit** → Permission/function key wiring

---

## 5. Operations Layer
**Purpose**: CLI scripts, update flows, and maintenance commands.

### Entries (placeholder)
- **flask update-permissions** → Sync permission catalog
- **flask update-addons** → Seed add-ons + backfill entitlements
- **flask update-subscription-tiers** → Sync tier limits

---

## Contribution Rules
1. Add new terms under the layer where they belong.
2. Link to the authoritative system doc for details.
3. Keep definitions concise (1–3 sentences).
4. Use consistent naming across layers (same term, same spelling).
