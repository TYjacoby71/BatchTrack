# 2026-02-17 — Documentation Guard Whole-File Coverage Clarification

## Summary
- Clarified guard/checklist language to explicitly require **entire touched-file** functional-header coverage for Python files.
- Removed wording ambiguity between “touched units” and “entire file coverage” in APP_DICTIONARY instructions.
- Improved guard failure wording so agents see that validation scope is file-wide, not hunk-limited.

## Problems Solved
- Agents could interpret checklist language as “document only modified functions/routes,” which conflicted with intended whole-file standards.
- APP_DICTIONARY instruction wording had mixed phrasing that could be read inconsistently.
- Guard output did not explicitly remind users that all top-level units in touched files are validated.

## Key Changes
- `.github/PULL_REQUEST_TEMPLATE.md`
  - Updated documentation checklist wording to explicitly state entire touched-file coverage for functional headers.
- `docs/DOCUMENTATION_STRUCTURE.md`
  - Updated PR checklist/enforcement wording to state whole-file validation for changed Python files.
- `docs/system/APP_DICTIONARY.md`
  - Updated Update Standard phrasing to “every top-level functional unit in a touched file.”
- `scripts/validate_pr_documentation.py`
  - Clarified Python schema validator comments and missing-header issue message to indicate whole-file scope.

## Files Modified
- `.github/PULL_REQUEST_TEMPLATE.md`
- `docs/DOCUMENTATION_STRUCTURE.md`
- `docs/system/APP_DICTIONARY.md`
- `scripts/validate_pr_documentation.py`
- `docs/changelog/2026-02-17-doc-guard-whole-file-coverage-clarification.md` (this file)
- `docs/changelog/CHANGELOG_INDEX.md`

