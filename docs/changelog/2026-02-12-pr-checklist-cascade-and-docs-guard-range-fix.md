# PR Checklist Cascade and Documentation Guard Range Fix

## Summary
Refined PR guidance into a sharper cascading checklist, added a one-line AI delegation phrase, and fixed documentation-guard push diff behavior that was producing noisy failures on multi-commit pushes.

## Problems Solved
- PR checklist instructions were split across sections and felt clunky for agent delegation.
- Teams had to over-specify repeated prompts ("did you run docs guard / dictionary / changelog") instead of using one reusable instruction.
- Documentation guard push runs used `HEAD~1`, which could mis-evaluate multi-commit pushes and surface misleading red X checks.

## Key Changes
- Reworked `.github/PULL_REQUEST_TEMPLATE.md` into an ordered cascade:
  1) System Integrity, 2) Scoping/Security, 3) Service/Domain, 4) User Impact, 5) Validation, 6) Documentation Integrity, 7) PR Readiness.
- Added explicit one-line AI shortcut phrase to standardize delegation.
- Synced `docs/DOCUMENTATION_STRUCTURE.md` checklist ordering and updated enforcement notes.
- Updated `.github/workflows/documentation-guard.yml` push mode to diff from `${{ github.event.before }}` (with safe fallback), not always `HEAD~1`.
- Updated `scripts/validate_pr_documentation.py` PR-level checks to validate changelog presence + index linkage while relying on dictionary coverage checks for app-path enforcement.

## Files Modified
- `.github/PULL_REQUEST_TEMPLATE.md`
- `docs/DOCUMENTATION_STRUCTURE.md`
- `.github/workflows/documentation-guard.yml`
- `scripts/validate_pr_documentation.py`

## Impact
- Makes "follow PR checklist instructions" a practical single prompt for AI agents.
- Reduces noisy documentation-guard failures on branch pushes with multiple commits.
- Keeps documentation requirements strict while focusing on relevance/coverage instead of mechanical file-touch rules.
