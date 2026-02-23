# Development Guide

## Synopsis
This guide captures the current engineering workflow and guardrails for changing BatchTrack safely. It focuses on service boundaries, multi-tenant scoping, permission/billing enforcement, and required documentation discipline.

## Glossary
- **Service authority**: The layer that owns domain behavior (routes orchestrate; services decide).
- **Tenant scoping**: Enforcing organization isolation through `organization_id` and permission context.
- **Docs guard**: `scripts/validate_pr_documentation.py` checks PR documentation/schema requirements.
- **Finalization pass**: Single end-of-change validation run (docs guard + tests) after implementation is complete.

## Core Engineering Rules

### 1) Keep route handlers thin
- Route files should validate input and call services.
- Domain logic belongs in service modules, not route bodies.

### 2) Respect tenant boundaries
- Scope tenant data by organization context.
- Never return cross-organization records to customer users.
- Developer access paths must be explicit and audited (masquerade/dev routes).

### 3) Enforce permissions + billing policy
- Use permission utilities/decorators (`require_permission`, `has_permission`).
- Do not hardcode role-name checks as authorization logic.
- Billing access gates are centralized through middleware and `BillingAccessPolicyService`.

### 4) Keep datetime handling consistent
- Use UTC-aware storage and comparisons.
- Use timezone helpers/filters for display conversion.
- See `TIMEZONE_SYSTEM.md` and `STORAGE_VS_DISPLAY.md`.

## Implementation Workflow

1. **Plan the change**
   - Identify owning service/module.
   - Identify permission/billing implications.
   - Identify data-scoping and migration impact.

2. **Implement in the correct layer**
   - Models: schema/state representation.
   - Services: business rules and orchestration.
   - Routes/blueprints: transport + authorization + response shape.
   - Templates/static: presentation only.

3. **Validate behavior**
   - Add/update tests where behavior changes.
   - Verify tenant isolation and permission outcomes.
   - Verify edge cases for batch/inventory/state transitions.

4. **Complete required documentation**
   - Update relevant `docs/system/*.md` files for current-state behavior changes.
   - Add dated changelog entry in `docs/changelog/` when you want release-history tracking for the change.
   - If a changelog entry is added, keep `docs/changelog/CHANGELOG_INDEX.md` linked.
   - Update APP_DICTIONARY coverage for touched app paths when applicable.

5. **Run validation tooling**
   - During iterative editing, do not run pytest/pip installs/docs guard unless explicitly requested.
   - During iterative editing, avoid repeated repo-wide validation loops and only run targeted debug checks when explicitly requested.
   - At finalization, run **one** validation pass for the change set:
     1. Stage changes.
     2. Run docs guard once on staged scope: `python3 scripts/validate_pr_documentation.py --staged`
     3. Run relevant tests once (targeted or full based on scope).
   - Only run `--full-link-check` when `docs/system/APP_DICTIONARY.md` changed or dictionary link targets moved.
   - If base-branch comparison is required, run `python3 scripts/validate_pr_documentation.py --base-ref origin/<base-branch>` once near final push.
   - Do not rerun successful full validations unless new commits materially change validated files.
   - For permission/add-on/tier updates, verify update scripts:
     - `flask update-permissions`
     - `flask update-addons`
     - `flask update-subscription-tiers`

## Common Anti-Patterns (Avoid)
- Directly mutating inventory/batch state in routes without service orchestration.
- Querying/scoping without organization context in customer-facing code.
- Authorization by UI visibility alone (must enforce server-side).
- Introducing parallel policy logic when a canonical service already exists.

## Relevance Check (2026-02-17)
Validated against:
- `app/middleware.py`
- `app/route_access.py`
- `app/utils/permissions.py`
- `app/services/inventory_adjustment/`
- `app/services/batch_service/`
- `app/scripts/commands/maintenance.py`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `scripts/validate_pr_documentation.py`
