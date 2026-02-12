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
`Follow PR checklist instructions in .github/PULL_REQUEST_TEMPLATE.md and do not stop until docs guard passes.`

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
- [ ] Tested locally
- [ ] Added/updated tests
- [ ] Ran `python3 scripts/validate_pr_documentation.py --base-ref origin/<base-branch>` and confirmed pass

### 6) Documentation and Knowledge Integrity
- [ ] Updated system docs for feature changes (`docs/system/`)
- [ ] Added/updated dated changelog entry when app behavior changed (`docs/changelog/YYYY-MM-DD-*.md`)
- [ ] Confirmed changelog index contains links to changed dated entries (`docs/changelog/CHANGELOG_INDEX.md`)
- [ ] Added/updated file Synopsis + Glossary blocks for every touched file
- [ ] Added Functional Unit headers (name/purpose/inputs/outputs, ≤5 sentences) for every touched top-level unit
- [ ] Updated APP_DICTIONARY.md for every added/moved/updated app term or location
- [ ] Verified one-entry rule (single canonical term entry, no duplicates)

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
