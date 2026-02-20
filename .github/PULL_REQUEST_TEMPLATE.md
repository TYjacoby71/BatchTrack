<!-- PR template for required summaries + checklists -->

## Description
<!-- Brief description of the changes -->

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Architecture change
- [ ] Documentation update

## Changes Made
<!-- List the key changes -->

## One-Line Instruction for AI Agents
Use this exact instruction when delegating PR prep:
`Follow PR checklist instructions in .github/PULL_REQUEST_TEMPLATE.md, apply docs/system/APP_DICTIONARY.md -> "Update Standard (Agent Instructions)" only where this PR changes behavior/files, and run docs guard once near finalization.`

## PR Checklist Instructions (Cascade order — top to bottom)

### 1) System Integrity
- [ ] Code follows project patterns
- [ ] No service layer bypassing

### 2) Scoping and Security
- [ ] Organization scoping maintained
- [ ] Permission checks in place
- [ ] Timezone handling is correct (STORAGE ≠ DISPLAY)

### 3) Service and Domain Correctness
- [ ] Update scripts considered (`update-permissions`, `update-addons`)
- [ ] Multi-tenant scenarios tested (if applicable)

### 4) User Impact
- [ ] For edited page templates/routes, metadata is updated in maker-first format (title, description, canonical, OG/Twitter tags when applicable)
- [ ] User-visible behavior and risk notes are captured in Description

### 5) Validation
- [ ] Tested locally (as appropriate for scope)
- [ ] Added/updated tests when behavior changed or a regression was fixed
- [ ] Ran `python3 scripts/validate_pr_documentation.py --base-ref origin/<base-branch>` near finalization and confirmed pass

### 6) Documentation and Knowledge Integrity
- [ ] Updated system docs for feature changes (`docs/system/`)
- [ ] Added/updated dated changelog entry when app Python behavior changed (`docs/changelog/YYYY-MM-DD-*.md`)
- [ ] Confirmed changelog index contains links to changed dated entries (`docs/changelog/CHANGELOG_INDEX.md`)
- [ ] Followed `docs/system/APP_DICTIONARY.md` -> **Update Standard (Agent Instructions)** for Synopsis + Glossary coverage on newly added or materially reworked files
- [ ] Followed `docs/system/APP_DICTIONARY.md` -> **Update Standard (Agent Instructions)** for top-level Functional Unit headers (Purpose/Inputs/Outputs) on changed/new units
- [ ] Followed `docs/system/APP_DICTIONARY.md` -> **Update Standard (Agent Instructions)** for added/moved/updated app Python terms and locations
- [ ] Verified APP_DICTIONARY one-entry rule (single canonical term entry, no duplicates)

### 7) PR Narrative and Review Readiness
- [ ] Description/Type/Changes are complete with rollout/rollback note
- [ ] Self-review completed; debug code and dead comments removed

## Evidence (Required)
- Base branch compared:
- Local commands run (copy/paste):
  - ``
- Documentation guard output:
  - ``
- Notes for reviewers (risk/edge cases/follow-ups):
