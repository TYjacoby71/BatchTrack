# AGENTS.md

## Synopsis
This file defines default execution behavior for coding agents in this repository. The default is implementation-only work with minimal overhead. Validation, test expansion, and PR-finalization steps run only when explicitly requested by the user.

## Glossary
- **Implementation mode**: Default mode for normal feature/bug work.
- **Finalization mode**: Explicit mode entered only when user says `finalize PR` (or equivalent).
- **Validation pass**: One-time targeted test run + one docs guard run.

## Agent Operating Policy

### 1) Default mode: Implementation mode
- Do implementation first.
- Do **not** add new regression tests by default.
- Do **not** run `pytest`, docs guard, or dependency-install loops by default.
- Do **not** run repeated validation loops.
- Prefer the smallest safe diff that satisfies the user request.

### 2) Enter finalization mode only on explicit user trigger
- Trigger phrase examples: `finalize PR`, `prepare PR`, `ready to finalize`.
- In finalization mode, do exactly one validation pass:
  1. Run targeted tests once.
  2. Run docs guard once (`python3 scripts/validate_pr_documentation.py --staged`).
  3. Commit and push once for that finalized state.
- Do not rerun full validations unless new commits changed validated files.

### 3) Test creation policy
- Do not create new test files unless the user explicitly requests tests.
- If tests are required, prefer updating existing focused tests over adding broad new suites.
- Add at most one focused regression test per bug fix unless user asks for more.

### 4) Cost-control policy
- Avoid exploratory “rethinking loops” that repeatedly rewrite the same area.
- Avoid duplicate command runs that do not add signal.
- Keep verification targeted to changed behavior only.
