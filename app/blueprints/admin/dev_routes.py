"""Legacy relocation marker for developer admin routes.

Synopsis:
Retain a lightweight compatibility marker indicating that developer-focused
admin routes were moved into the dedicated developer blueprint module.

Glossary:
- Relocation marker: Non-executable module documenting moved route ownership.
- Developer blueprint: Canonical namespace for developer management routes.
- Legacy admin module: Historical location kept to avoid accidental reuse.
"""

# --- Legacy relocation notice ---
# Purpose: Document that this module no longer hosts executable route handlers.
# Inputs: None.
# Outputs: Maintainer-facing guidance pointing to replacement module path.
# Moved to: `app/blueprints/developer/routes.py`.
