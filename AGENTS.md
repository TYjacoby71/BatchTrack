# Agent Execution Policy

This repository uses a finalization-first workflow.

## Default mode (implementation)
- Implement requested code changes first.
- Do **not** run full validation loops during implementation.
- Do **not** run dependency installs during implementation.

## Commands forbidden unless explicitly requested by the user
- `pytest`
- `python -m pytest`
- `python3 -m pytest`
- `pip install ...`
- `python3 -m pip install ...`
- `pre-commit run ...`
- `python3 scripts/validate_pr_documentation.py ...`

## Allowed during implementation
- Read/search/edit files.
- Syntax-only checks for directly edited files (for example `python3 -m py_compile ...`) when helpful.
- Small targeted debug checks **only** when the user explicitly asks.

## Finalization mode
Only when the user explicitly says **"finalize"** (or clearly asks for final verification):
1. Run tests once (targeted or full based on change scope).
2. Run docs guard once.
3. Report results.

Do not repeat test/guard/install loops unless the user requests another pass.
