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

## Testing
- [ ] Tested locally
- [ ] Added/updated tests
- [ ] Tested multi-tenant scenarios (if applicable)

## Documentation
- [ ] Updated system docs for feature changes (`docs/system/`)
- [ ] Added/updated dated changelog entry (`docs/changelog/YYYY-MM-DD-*.md`)
- [ ] Updated changelog index (`docs/changelog/CHANGELOG_INDEX.md`)
- [ ] Updated add-on entitlements doc if tiers/add-ons changed
- [ ] Added/updated file Synopsis + Glossary blocks for every touched file
- [ ] Added Functional Unit headers (name/purpose/inputs/outputs, ≤5 sentences) for every touched top-level unit
- [ ] Updated APP_DICTIONARY.md for every added/moved/updated app term or location
- [ ] Verified one-entry rule (single canonical term entry, no duplicates)
- [ ] Ran `python3 scripts/validate_pr_documentation.py` and confirmed pass

## PR Workflow Gate (Required, in order — if any item is unchecked, PR is not merge-ready)
- [ ] **Step 1: Scope is clear** — Description/Type/Changes are complete, with user impact and rollback note.
- [ ] **Step 2: Branch discipline is respected** — work is on the feature branch only, with focused commits and no unrelated file edits.
- [ ] **Step 3: Validation is complete** — relevant local tests/checks were run for touched areas and passed.
- [ ] **Step 4: Documentation guard is green** — `python3 scripts/validate_pr_documentation.py --base-ref origin/<base-branch>` passed.
- [ ] **Step 5: Review readiness is complete** — self-review done, debug code removed, and CI checks are green.

## Checklist
- [ ] Code follows project patterns
- [ ] No service layer bypassing
- [ ] Organization scoping maintained
- [ ] Timezone handling correct (STORAGE ≠ DISPLAY)
- [ ] Permission checks in place
- [ ] Update scripts considered (`update-permissions`, `update-addons`)
- [ ] For any edited page templates/routes, metadata is updated in maker-first format (title, description, canonical, OG/Twitter tags when applicable)

## Evidence (Required)
- Base branch compared:
- Local commands run (copy/paste):
  - ``
- Documentation guard output:
  - ``
- Notes for reviewers (risk/edge cases/follow-ups):
