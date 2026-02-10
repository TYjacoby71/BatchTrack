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
