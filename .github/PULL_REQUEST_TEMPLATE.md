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
`Implement feature work first. Do not run pytest, pip install, or docs guard during implementation unless explicitly requested. When I say "finalize", run one finalization pass only: update APP_DICTIONARY/glossary requirements for changed scope, run tests once, then run docs guard once (prefer --staged). Do not repeat full validations unless new commits change validated files.`

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
- [ ] During implementation, do not run pytest/pip install/docs-guard unless explicitly requested (targeted debug checks only when requested)
- [ ] During implementation, avoid repeated repo-wide validation loops
- [ ] At finalization, run tests once (targeted or full, as appropriate) and add/update tests when behavior changed or a regression was fixed
- [ ] At finalization, run `python3 scripts/validate_pr_documentation.py --staged` once and confirm pass
- [ ] If base-branch comparison is needed, run `python3 scripts/validate_pr_documentation.py --base-ref origin/<base-branch>` once (instead of repeating staged + base-ref in loops)
- [ ] Run `--full-link-check` only when APP_DICTIONARY links/paths changed or for release-level hardening

### 6) Documentation and Knowledge Integrity
- [ ] Updated system docs for feature changes (`docs/system/`)
- [ ] Followed `docs/system/APP_DICTIONARY.md` -> **Update Standard (Agent Instructions)** for Synopsis + Glossary coverage on newly added or materially reworked files
- [ ] Updated APP_DICTIONARY locations for added/moved/updated app Python terms and paths
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
