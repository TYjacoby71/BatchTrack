# Documentation Structure

## Synopsis
This document explains where documentation lives and how updates should be staged across system guides, changelogs, and checklists.

## Glossary
- **System doc**: Current-state guide for a platform area.
- **Changelog**: Historical record of changes.

## Directory Structure

```
docs/
├── system/              Master documentation for every platform system and concept
│   ├── ARCHITECTURE.md
│   ├── ADDONS_AND_ENTITLEMENTS.md
│   ├── APP_DICTIONARY.md
│   ├── SERVICES.md
│   ├── DATABASE_MODELS.md
│   ├── PLAN_SNAPSHOT.md
│   ├── API_REFERENCE.md
│   ├── DEVELOPMENT_GUIDE.md
│   ├── deploy_migration_guide.md
│   ├── PUBLIC_TOOLS.md
│   ├── EXPORTS.md
│   ├── FREE_TIER.md
│   ├── TRACKING_PLAN.md
│   ├── CURRENTLY_STUBBED.md
│   ├── DEPRECATED_FEATURES.md
│   ├── GLOBAL_ITEM_LIBRARY.md
│   ├── CONTAINERS_CURATION.md
│   ├── CONTAINER_NAMING.md
│   ├── GLOBAL_ITEM_JSON_STRUCTURE.md
│   ├── INVENTORY_EVENTS_TERMINOLOGY.md
│   ├── TIMEZONE_SYSTEM.md
│   ├── STORAGE_VS_DISPLAY.md
│   └── USERS_AND_PERMISSIONS.md
│
├── todo/                Launch readiness, QA, and immediate action lists
│   ├── CRITICAL_PRELAUNCH.md
│   ├── LAUNCH_RUNBOOK.md
│   ├── FIX_IMMEDIATE.md
│   ├── RETENTION_CANCELLATION_QA.md
│   ├── INVENTORY_UPGRADE_QA.md
│   ├── INVENTORY_COST_QA.md
│   └── UNIT_MAPPING_QA.md
│
├── changelog/           Complete history of changes
│   ├── CHANGELOG_INDEX.md
│   └── YYYY-MM-DD-description.md
│
├── refactor/            Refactoring documentation and progress logs
│   └── (various refactor docs)
│
└── (root level)         Indexes, future planning, and special studies
    ├── DOCUMENTATION_STRUCTURE.md
    ├── FUTURE_ROADMAP.md
    ├── original-styling-analysis.md
    └── (additional one-off analyses)
```

Marketing documentation that describes the content workspace now lives in `marketing/README.md` alongside the site assets.

## Document Categories

### 1. System Documentation (`docs/system/`)
**Purpose**: Describe HOW the system works (current state)

**Types**:
- Architecture documents (ARCHITECTURE.md, SERVICES.md)
- Feature guides (TIMEZONE_SYSTEM.md, GLOBAL_ITEM_LIBRARY.md)
- Best practices (STORAGE_VS_DISPLAY.md)
- Data structures (DATABASE_MODELS.md)
- Protocols (WALL_OF_DRAWERS_PROTOCOL.md)

**Update when**: System design or behavior changes

### 2. Change Logs (`docs/changelog/`)
**Purpose**: Track WHAT changed and WHEN

**Types**:
- Individual change logs (YYYY-MM-DD-description.md)
- Changelog index (CHANGELOG_INDEX.md)

**Update when**: You want durable release/change-history tracking for code changes, bug fixes, or improvements

### 3. System Documentation (`docs/system/`)
**Purpose**: Single library for developers to understand any platform area

**Types**:
- Architecture and service authority guides
- API contracts and public integrations
- Product program references (tiers, exports, analytics)
- Operational runbooks (deployments, error handling)
- Domain language and data structure glossaries

**Update when**: Any system behavior, developer workflow, or external contract changes

### 4. To-Do and QA (`docs/todo/`)
**Purpose**: Track actionable checklists (launch, QA, urgent fixes)

**Types**:
- Launch readiness plans (CRITICAL_PRELAUNCH.md, LAUNCH_RUNBOOK.md)
- QA scripts and validation suites
- Immediate fix lists and operational runbooks

**Update when**: Launch scope, QA coverage, or urgent task lists change

### 5. Root Level Documentation
**Purpose**: Product management, deployment, and general reference guides

**Types**:
- Documentation map (this file)
- Long-range roadmap and ideation docs
- One-off analyses and research notes

**Update when**: Cross-team processes or long-range planning changes

## Documentation Rules

### ✅ DO

1. **System docs describe current state**
   - Focus on HOW things work now
   - Remove outdated information
   - Keep examples current

2. **Changelogs record history**
   - Include what changed, when, and why
   - Show code examples
   - List files modified

3. **Update relevant docs when making changes**
   - System docs: Update to reflect new state
   - Changelog: Optional release-history record when desired

4. **Document Functional Units in code (optional style guidance)**
   - Add a section header for each top-level functional unit (no numbering)
   - Include: unit name, purpose, inputs, outputs
   - Keep each description to 5 sentences or fewer
   - Use the same pattern for route handlers, service methods, scripts, and models

### ❌ DON'T

1. **Don't put change history in system docs**
   - System docs are timeless guides
   - Historical changes belong in changelog/

2. **Don't create duplicate documentation**
   - Each piece of information has ONE home
   - Use links for cross-references

3. **Don't create unnecessary iteration logs**
   - Work-in-progress logs are temporary
   - Only keep finished documentation

## Functional Unit Header Standard (Optional Style Guide)

**Term to use**: "Top-Level Functional Unit"

**When**: Use for larger refactors/new modules when helpful for readability; this is not required by the docs guard.

**Header structure**:
```
# --- <UNIT NAME> ---
# Purpose: <Concise description (≤ 5 sentences)>
# Inputs: <Key inputs, parameters, or request payloads>
# Outputs: <Return values, side-effects, or response payloads>
```

**Naming by file type**:
- Route files: use "Route Handler" or "Endpoint"
- Service files: use "Service Method" or "Utility Function"
- Model files: use "Model" or "Schema"

## When to Update Documentation

```
Made a code change?
    ↓
1. (Optional) Add entry to docs/changelog/YYYY-MM-DD-description.md
    - What was changed
    - Why it was changed
    - Files affected
    - Examples
    ↓
2. Update docs/system/ (if design changed)
    - Update architecture docs (ARCHITECTURE.md, SERVICES.md, DATABASE_MODELS.md)
    - Refresh feature guides and domain glossaries
    - Revise API_REFERENCE.md when contracts change
    - Update DEVELOPMENT_GUIDE.md and deploy_migration_guide.md for workflow changes
    ↓
3. Update root docs (if needed)
    - DOCUMENTATION_STRUCTURE.md when map or ownership shifts
    - FUTURE_ROADMAP.md and other planning docs when strategy evolves
```

## PR Documentation Checklist (keep in sync with PR template)
- [ ] 1) **System Integrity** — project patterns respected; no service-layer bypassing.
- [ ] 2) **Scoping and Security** — org scoping, permission checks, and timezone handling are correct.
- [ ] 3) **Service and Domain Correctness** — update scripts considered and multi-tenant behavior tested when relevant.
- [ ] 4) **User Impact** — metadata and user-visible behavior/risk notes are updated.
- [ ] 5) **Validation** — during iterative editing, do not run pytest/pip install/docs-guard unless explicitly requested and avoid repeated repo-wide loops; at finalization run one validation pass: tests once (as appropriate), docs guard once (`python3 scripts/validate_pr_documentation.py --staged`), and only use `--full-link-check` when dictionary links/paths changed.
- [ ] 6) **Documentation and Knowledge Integrity** — system docs + follow APP_DICTIONARY head instruction block for Synopsis/Glossary and app Python terms/locations + one-entry rule.
- [ ] 7) **PR Narrative and Readiness** — description/type/changes complete with rollout/rollback note, plus reviewer evidence.

### AI Shortcut Phrase
Use this exact delegation phrase:
`Implement feature work first. Do not run pytest, pip install, or docs guard during implementation unless explicitly requested. When I say "finalize", run one finalization pass only: update APP_DICTIONARY/glossary requirements for changed scope, run tests once, then run docs guard once (prefer --staged). Do not repeat full validations unless new commits change validated files.`

## Enforcement (Automated Guard)

The following rules are enforced by `scripts/validate_pr_documentation.py` during finalization runs:

1. **App Python change requirement**
   - Changed app Python file paths must be covered in `APP_DICTIONARY.md`.

2. **Python schema requirement (`app/` and `scripts/`)**
   - New Python modules must include both **Synopsis** and **Glossary** in the module docstring.

3. **Dictionary schema requirement**
   - Entry format: `- **Term** → Description`.
   - One-entry rule: one canonical dictionary entry per unique term.
   - Every changed `app/**/*.py` file path must be referenced in `APP_DICTIONARY.md`.
   - File links/locations in dictionary entries are validated when `APP_DICTIONARY.md` is edited.

4. **Doc schema requirement**
   - Changed `docs/system/*.md` files must include `## Synopsis` and `## Glossary`.

## Cross-References

- Main README → Points to docs/system/ and other docs
- System docs → Cross-reference each other
- System docs → Link to changelog/ for history
- Changelog → References system docs being changed

## Examples

### Good: Clear Separation

**docs/system/TIMEZONE_SYSTEM.md** (System guide)
```markdown
# Timezone System

## How It Works
All datetimes are stored as timezone-aware UTC...

## Usage
Use `datetime.now(timezone.utc)` for storage...
```

**docs/changelog/2025-10-28-timezone-standardization.md** (Change log)
```markdown
# Timezone Standardization

## What Changed
- Fixed TimezoneUtils.utc_now() to return timezone-aware datetimes
- Updated 48 model columns across 17 files
...
```

### Bad: Mixed Concerns

**docs/system/TIMEZONE_SYSTEM.md** (Don't do this)
```markdown
# Timezone System

## Recent Changes (2025-10-28)
- Fixed bug in utc_now()
- Updated all models
...

## How It Works
...
```

## Maintenance

- Review docs quarterly for accuracy
- Archive outdated changelog entries if needed
- Keep system docs focused and current
- Remove duplicate information

---

**Last Updated**: 2025-11-04
