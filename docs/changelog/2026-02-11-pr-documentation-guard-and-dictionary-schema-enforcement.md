# PR Documentation Guard + Dictionary Schema Enforcement

## Summary
Added an automated documentation guard that enforces synopsis/glossary coverage, top-level functional unit headers, dictionary alignment, changelog linkage, and one-entry dictionary term uniqueness.

## Problems Solved
- PR checklist requirements were advisory and easy to skip under time pressure.
- Dictionary updates for added/moved app surfaces were inconsistent, causing stale paths and missing definitions.
- There was no automated way to verify that changed files included required Synopsis/Glossary and functional-unit metadata.

## Key Changes
- Added `scripts/validate_pr_documentation.py`:
  - validates changed-file requirements against git diff/staged sets,
  - enforces module `Synopsis` + `Glossary` sections for `app/` and `scripts/` Python files,
  - enforces top-level functional unit comment headers (`# ---`, `# Purpose`, `# Inputs`, `# Outputs`),
  - requires dictionary + changelog updates when `app/` files change,
  - validates dictionary entry schema and duplicate-term one-entry rule,
  - validates dictionary/changelog index link targets.
- Added CI enforcement workflow:
  - `.github/workflows/documentation-guard.yml`
- Added local enforcement hooks:
  - `Makefile` target: `docs-guard`
  - `.pre-commit-config.yaml` local hook running guard on staged changes
- Updated policy/checklist docs to match enforcement:
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `docs/DOCUMENTATION_STRUCTURE.md`
  - `docs/system/APP_DICTIONARY.md`
- Added missing class-level functional headers in developer services:
  - `OrganizationService`
  - `UserService`
- Added missing dictionary coverage for prior signup-template change:
  - `app/templates/pages/auth/signup.html`

## Files Modified
- `.github/workflows/documentation-guard.yml` (new)
- `scripts/validate_pr_documentation.py` (new)
- `Makefile`
- `.pre-commit-config.yaml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `docs/DOCUMENTATION_STRUCTURE.md`
- `docs/system/APP_DICTIONARY.md`
- `docs/changelog/CHANGELOG_INDEX.md`
- `app/services/developer/organization_service.py`
- `app/services/developer/user_service.py`

## Impact
- PRs now fail early when documentation, dictionary, or changelog standards are incomplete.
- Enforces one canonical dictionary entry per term and keeps file-path/location links current.
- Reduces drift between app changes and system documentation, improving both human and AI-agent reliability.
