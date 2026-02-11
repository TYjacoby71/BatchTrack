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
