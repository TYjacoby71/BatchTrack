# Documentation Structure

## Overview

This document explains the organization of BatchTrack documentation.

## Directory Structure

```
docs/
├── system/              System architecture and feature documentation
│   ├── ARCHITECTURE.md
│   ├── SERVICES.md
│   ├── DATABASE_MODELS.md
│   ├── TIMEZONE_SYSTEM.md
│   ├── STORAGE_VS_DISPLAY.md
│   ├── USERS_AND_PERMISSIONS.md
│   ├── GLOBAL_ITEM_LIBRARY.md
│   ├── CONTAINERS_CURATION.md
│   ├── WALL_OF_DRAWERS_PROTOCOL.md
│   ├── CONTAINER_NAMING.md
│   ├── GLOBAL_ITEM_JSON_STRUCTURE.md
│   └── INVENTORY_EVENTS_TERMINOLOGY.md
│
├── changelog/           Complete history of changes
│   ├── README.md
│   └── YYYY-MM-DD-description.md
│
├── refactor/            Refactoring documentation
│   └── (various refactor docs)
│
└── (root level)         Project management and QA docs
    ├── API_REFERENCE.md
    ├── DEVELOPMENT_GUIDE.md
    ├── CRITICAL_PRELAUNCH.md
    ├── LAUNCH_RUNBOOK.md
    ├── FUTURE_ROADMAP.md
    ├── TRACKING_PLAN.md
    ├── *_QA.md (QA documents)
    └── etc.
```

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
- Changelog index (README.md)

**Update when**: Making any code changes, bug fixes, or improvements

### 3. Root Level Documentation
**Purpose**: Project management, deployment, QA, and general guides

**Types**:
- Development guides
- API documentation
- Launch checklists
- QA test plans
- Future roadmap
- Tracking plans

**Update when**: Process, deployment, or testing procedures change

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

3. **Update both when making changes**
   - Changelog: Record the change
   - System docs: Update to reflect new state

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

## When to Update Documentation

```
Made a code change?
    ↓
1. Add entry to docs/changelog/YYYY-MM-DD-description.md
    - What was changed
    - Why it was changed
    - Files affected
    - Examples
    ↓
2. Update docs/system/ (if design changed)
    - Update architecture docs
    - Update feature guides
    - Update best practices
    ↓
3. Update root docs (if needed)
    - API_REFERENCE.md if API changed
    - DEVELOPMENT_GUIDE.md if process changed
```

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

**Last Updated**: 2025-10-28
