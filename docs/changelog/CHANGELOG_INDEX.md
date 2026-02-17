# Change Log Index

This directory contains the complete history of all fixes, improvements, and changes to the BatchTrack codebase.

## Purpose

- Track **WHAT** changed and **WHEN**
- Document problems fixed
- Record files modified
- Show code examples and impact analysis

## Change Logs

### 2026

#### February
- **[2026-02-17: Inventory Quantity Locking and Infinite Toggle Lot Drain](2026-02-17-inventory-quantity-locking-and-infinite-toggle-drain.md)**
  - Locked quantity adjustment/recount surfaces behind `inventory.track_quantities` with upgrade bounce behavior.
  - Forced create flows in quantity-locked tiers to open in infinite mode without opening quantity input.
  - Added tracked -> infinite lot drain behavior with audit-history logging.
- **[2026-02-17: Split Inventory Quantity Tracking from Batch Output Permission](2026-02-17-split-inventory-quantity-tracking-from-batch-output-permission.md)**
  - Added new `inventory.track_quantities` entitlement to separate deduction quantity behavior from batch output posting.
  - Refactored inventory/stock-check quantity-tracking policy checks to use inventory-scoped entitlement logic.
  - Updated pricing feature catalog rows to present quantity tracking and batch output posting as distinct capabilities.
- **[2026-02-17: Infinite Inventory Guardrail + Route Documentation Compliance](2026-02-17-infinite-inventory-guardrail-route-doc-compliance.md)**
  - Added required functional-unit header metadata on touched batch and production-planning route modules.
  - Added missing APP_DICTIONARY coverage entries for touched route files.
  - Restored latest-commit Documentation Guard compliance for changelog + dictionary checks.
- **[2026-02-17: Recipe Lineage UI + Documentation Guard Alignment](2026-02-17-recipe-lineage-ui-doc-guard-alignment.md)**
  - Split recipe lineage actions into dedicated New Test/New Variation flows and simplified lineage view surfaces.
  - Hardened variation naming and promotion naming behavior for recipe-group consistency.
  - Added documentation schema/dictionary updates required for Documentation Guard compliance.
- **[2026-02-17: Tier Presentation Documentation Guard Compliance](2026-02-17-tier-presentation-documentation-guard-compliance.md)**
  - Added required function/class header schema blocks across the new tier presentation package and related pricing/signup services.
  - Added missing module synopsis/glossary coverage for new package modules.
  - Added APP_DICTIONARY coverage for `tier_presentation` paths and signup plan catalog service.
- **[2026-02-16: Pricing Feature Catalog-Driven Comparison Table](2026-02-16-pricing-feature-catalog-driven-comparison-table.md)**
  - Replaced raw permission-style pricing rows with grouped customer-facing feature and limit sections.
  - Added tier metadata plumbing for limits, add-ons, and retention policy rendering.
  - Updated pricing page comparison UI to support boolean and text cells.
- **[2026-02-16: Tier Feature Catalog and Entitlement Mapping Rules](2026-02-16-tier-feature-catalog-and-mapping-rules.md)**
  - Added a customer-facing feature taxonomy mapped to permissions, add-ons, flags, and limits.
  - Documented which tier limits are currently hard-enforced versus metadata-only.
  - Added tier-construction dependency rules for multi-user, BatchBot, marketplace, retention, and bulk operations.
- **[2026-02-16: Recipe Variation Promotion Name and Group Visibility Fixes](2026-02-16-recipe-variation-promotion-name-and-group-visibility-fixes.md)**
  - Restored canonical master/variation names when promoting test versions to current.
  - Switched recipe list variation rendering to recipe-group lineage scope so master migrations keep variation visibility.
  - Added regression tests for promotion naming and post-promotion variation display.
- **[2026-02-14: Soap Backend Policy Injection + Recipe Payload API](2026-02-14-soap-backend-policy-and-recipe-payload-api.md)**
  - Moved soap policy/constants ownership to backend-injected config consumed by frontend runtime modules.
  - Added `/tools/api/soap/recipe-payload` and `/tools/api/soap/quality-nudge` so payload composition and quality nudging are backend authoritative.
  - Preserved existing soap display while replacing JS-built advisory shells with template-driven DOM rendering.
- **[2026-02-14: Soap Print Fill Confirmation Modal](2026-02-14-soap-print-fill-confirmation-modal.md)**
  - Added a print-time mold-fill confirmation modal to the Soap Formulator print finalization flow.
  - Added optional normalize-and-print scaling to fit a user-selected mold-fill percentage.
  - Kept reactive stage editing unchanged while moving mold-fit confirmation to print time.
- **[2026-02-14: Soap Guidance Dock Consolidation (Stage + Quality Hint Unification)](2026-02-14-soap-guidance-dock-consolidation.md)**
  - Consolidated scattered soap stage/quality hints into one bottom guidance dock with active-hint summary.
  - Added upward-expanding overlay guidance panel with caret toggle while keeping action controls in one place.
  - Rerouted dynamic hint/warning/tip writers to a centralized guidance manager and removed in-card hint duplication.
- **[2026-02-14: Soap Events Modularization](2026-02-14-soap-events-modularization.md)**
  - Split soap event orchestration into focused modules for rows, forms, exports, mobile drawer behavior, and initialization.
  - Replaced the previous large events file with a thin orchestrator layer.
  - Updated hashed soap bundle output and manifest mapping to ship the refactor.
- **[2026-02-13: Timer Datetime Rendering Fixes](2026-02-13-timer-datetime-rendering-fixes.md)**
  - Fixed timezone-mixed timer math on batch in-progress rendering paths.
  - Hardened timer management timestamp parsing to prevent `NaN` countdown output.
  - Added targeted regression tests for timer display stability.
- **[2026-02-12: Soap Tool Service Orchestration and JS Thinning](2026-02-12-soap-tool-service-orchestration-and-js-thinning.md)**
  - Added a dedicated `app/services/tools/soap_tool/` package to compile lye/water, additives, quality report data, and export payloads in one backend authority.
  - Updated `/tools/api/soap/calculate` and front-end runner wiring to consume service-computed bundles instead of duplicating calculations in JS.
  - Moved formula CSV/print-sheet source payload generation into backend compute outputs for consistency.
- **[2026-02-12: PR Checklist Cascade and Documentation Guard Range Fix](2026-02-12-pr-checklist-cascade-and-docs-guard-range-fix.md)**
  - Reordered PR checklist instructions into a cascading, single-pass sequence for clearer agent delegation.
  - Added one-line AI shortcut phrasing for "follow PR checklist instructions" handoffs.
  - Fixed documentation-guard push diff range to evaluate full push sets instead of only `HEAD~1`.
- **[2026-02-11: Soap Formulator Service Package + UI Stability](2026-02-11-soap-formulator-service-package-and-ui-stability.md)**
  - Added a dedicated tool-scoped soap calculator service package with typed contracts and canonical lye/water computations.
  - Wired the public soap formulator to a structured `/tools/api/soap/calculate` endpoint and removed duplicated frontend lye/water math.
  - Completed targeted soap UI fixes for stage synchronization, card scrolling, marker visibility, and field suffix/icon overlap.
- **[2026-02-12: Homepage Brand Logo and Favicon Integration](2026-02-12-homepage-brand-logo-and-favicon-integration.md)**
  - Added stable branding asset routes for full logo and square app tile SVGs.
  - Added a cropped full-logo header route and bumped homepage cache key so logo updates render immediately.
  - Replaced text-only shared header brand labels with the full logo image.
  - Wired homepage/public shell favicon links to the square app tile.
- **[2026-02-11: Stripe Cancellation During Customer Deletion](2026-02-11-stripe-cancellation-on-customer-deletion.md)**
  - Added pre-delete Stripe cancellation guard for organization hard-delete and final-customer hard-delete.
  - Deletions now abort when Stripe cancellation fails to prevent orphan billing.
  - Added tests covering both success and failure cancellation paths.
- **[2026-02-11: Billing Access Policy Extraction + Inactive Organization Lockout](2026-02-11-billing-access-policy-and-inactive-org-lockout.md)**
  - Fixed `/billing/upgrade` redirect-loop behavior for recoverable billing states.
  - Extracted billing access decisions into `BillingAccessPolicyService` and simplified middleware responsibilities.
  - Enforced consistent hard-lock login/session behavior for inactive organizations.
- **[2026-02-11: PR Documentation Guard + Dictionary Schema Enforcement](2026-02-11-pr-documentation-guard-and-dictionary-schema-enforcement.md)**
  - Added automated guard for synopsis/glossary headers, functional-unit blocks, and dictionary/changelog alignment.
  - Enforced one-entry dictionary term uniqueness and link/path validation.
  - Wired enforcement into CI, pre-commit, and Makefile quality flow.
- **[2026-02-11: Deletion Hard-Delete Safety + Legacy Marketplace Archive](2026-02-11-deletion-hard-delete-safety-and-legacy-archive.md)**
  - Hardened organization hard-delete to run scoped FK-safe cleanup and avoid stale cross-org references.
  - Added marketplace/listed/sold recipe JSON snapshot export before organization deletion.
  - Added developer user hard-delete endpoint and modal confirmation flow for test-account cleanup.
- **[2026-02-10: Staging Homepage Variant Toggle in Public Nav](2026-02-10-staging-homepage-variant-nav-toggle.md)**
  - Added a staging-only "Home Variants" dropdown in public navigation.
  - Added quick links to classic homepage, `/lp/hormozi`, and `/lp/robbins`.
  - Added tests ensuring visibility only in staging.
- **[2026-02-10: SEO Guide Agent Update Standard Clarification](2026-02-10-seo-guide-agent-update-standard.md)**
  - Added dictionary-style top-of-file instructions for metadata implementation.
  - Clarified when to apply the guide vs when to edit the guide itself.
  - Added a pre-push metadata quality checklist for touched routes/templates.
- **[2026-02-10: Landing Page A/B Variants + Metadata/Dictionary Alignment](2026-02-10-landing-page-ab-variants-and-metadata-dictionary-alignment.md)**
  - Added `/lp/hormozi` and `/lp/robbins` public landing pages for messaging A/B tests.
  - Added explicit maker-first metadata context and OG image mapping for both landing routes.
  - Updated APP_DICTIONARY entries for new routes and landing UI surfaces.
- **[2026-02-10: Tools Index Visual Cleanup and Mobile Theme Fallback Fix](2026-02-10-tools-index-visual-cleanup-and-mobile-theme-fallback.md)**
  - Removed rainbow-like category accents from `/tools` and aligned cards/tiles to core app styling.
  - Fixed mobile dark-theme forcing by requiring explicit system-theme mode and adding light fallback.
  - Added dictionary/changelog documentation for updated tool UI and theme semantics.
- **[2026-02-10: Pricing Page Launch, Public CTA Routing, and Header Offset Fix](2026-02-10-pricing-page-and-public-cta-flow.md)**
  - Added dedicated `/pricing` sales page with lifetime-first display and 3-tier checkbox comparison.
  - Rewired public pricing/trial links to deterministic `/pricing` → `/auth/signup` flow.
  - Removed development/waitlist gating from homepage CTAs and fixed public header offset CSS conflicts.
- **[2026-02-10: Auth Email Modes and Integrations Checklist Alignment](2026-02-10-auth-email-modes-and-integrations-checklist.md)**
  - Added env-driven auth-email verification/reset controls with provider-aware legacy fallback.
  - Updated developer integrations checklist to show configured vs effective auth-email mode.
  - Documented new routes/terms in APP_DICTIONARY and operations FAQ.

- **[2026-02-09: Lifetime Billing Alignment and Stripe Runbook](2026-02-09-lifetime-billing-single-key-runbook.md)**
  - Aligned checkout to single-key tier model with derived yearly/lifetime lookup keys.
  - Documented Stripe production setup and safe price-update runbook.
  - Simplified tier admin by removing tier type selector from edit flow.

- **[2026-02-06: Recipe Lineage Notes, Prefix Auto-Generation, and Edit Overrides](2026-02-06-recipe-lineage-notes-and-prefixes.md)**
  - Auto-generated recipe prefixes and org-scoped lineage IDs.
  - Recipe notes panel, published-edit confirmation, and new group naming control.

### 2025

#### November
- **[2025-11-24: BatchBot Refills & Usage Limits](2025-11-24-batchbot-refills-and-limits.md)**
  - Separate chat vs action quotas, Stripe-powered refill add-on, and dashboard prompts.
  - Public vs paid Batchley experiences clarified for homepage vs authenticated users.
  - Developer checklist updated with new AI env variables and refill lookup key.

#### October
- **[2025-10-28: Timezone Standardization](2025-10-28-timezone-standardization.md)**
  - Complete timezone system overhaul
  - Timezone-aware datetime storage
  - Auto-detection and smart timezone selection
  - Storage vs Display separation
  - Bugbot TypeError fix

---

## Adding New Entries

When documenting changes:

1. Create file: `YYYY-MM-DD-brief-description.md`
2. Include:
   - Summary of what changed
   - Problems fixed
   - Files modified
   - Impact analysis
   - Code examples
3. Add link to this index

---

**Note**: System documentation in [../system/](../system/) describes HOW the system works.  
This directory tracks WHAT changed and WHEN.
