# Free Tier Access and Gating

## Synopsis
This document describes how the default free customer tier is currently enforced through permissions, middleware billing policy, and public-route boundaries.

## Glossary
- **Free tier**: Seeded customer tier named `Free Tools`.
- **Permission gate**: Route/service authorization check (for example `inventory.adjust`, `batches.create`).
- **Public surface**: Routes intentionally reachable without authentication.

## Current Tier Definition
The default seeded free tier is `Free Tools` and is configured in `subscription_seeder` as a billing-exempt starter tier with limited permissions.

Default free-tier permissions include recipe authoring + inventory read:
- `recipes.view`
- `recipes.create`
- `recipes.edit`
- `recipes.delete`
- `inventory.view`

Not included by default:
- `inventory.adjust`
- `batches.create`
- `reports.export`
- most advanced product/alerts/integration capabilities

## How Gating Works

### 1) Permission-based enforcement
- Route decorators and permission utilities enforce action rights server-side.
- UI may hide controls, but backend permission checks are authoritative.

### 2) Billing-policy enforcement
- Middleware consults `BillingAccessPolicyService`.
- Recoverable billing states redirect to `/billing/upgrade`.
- Hard-lock states force logout + deny access.

### 3) Public unauthenticated surfaces
By route-access config, anonymous users can access:
- `/tools` and tool subroutes
- `/exports/tool/*`
- public API endpoints under `/api/public/*`
- public marketing/legal/auth pages
- public global library pages (`/global-items`) when feature-enabled

## Free/Guest Quota Note
Soap draft submissions from public tools are quota-limited for guest/free contexts (rolling 24-hour window) in tools route logic.

## Relevance Check (2026-02-17)
Validated against:
- `app/seeders/subscription_seeder.py`
- `app/utils/permissions.py`
- `app/middleware.py`
- `app/services/billing_access_policy_service.py`
- `app/route_access.py`
- `app/blueprints/tools/routes.py`
