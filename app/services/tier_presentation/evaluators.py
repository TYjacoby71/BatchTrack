"""Rule evaluators for tier presentation rows.

Synopsis:
Evaluates declarative row rules against normalized tier facts to produce
comparison cell payloads.

Glossary:
- Entitlement match: Permission/add-on/function rule that enables a row.
- Row spec: Declarative definition from the tier presentation catalog.
"""

from __future__ import annotations

from typing import Any

from .formatters import format_numeric_limit, format_retention_cell
from .helpers import coerce_int, normalize_token_set


# --- Match tier against row spec ---
# Purpose: Evaluate entitlement and limit predicates for one tier/row pair.
# Inputs: Tier fact dictionary and declarative row specification dictionary.
# Outputs: True when the tier satisfies all row requirements; otherwise False.
def tier_matches_row_spec(*, tier: dict[str, Any], row_spec: dict[str, Any]) -> bool:
    """Return True when the tier satisfies row entitlement and limit rules."""
    permission_set = set(tier.get("permission_set") or set())
    addon_key_set = set(tier.get("addon_key_set") or set())
    addon_function_set = set(tier.get("addon_function_set") or set())
    limits = tier.get("limits") or {}

    permissions_any = normalize_token_set(row_spec.get("permissions_any"))
    permissions_all = normalize_token_set(row_spec.get("permissions_all"))
    addon_keys_any = normalize_token_set(row_spec.get("addon_keys_any"))
    addon_functions_any = normalize_token_set(row_spec.get("addon_functions_any"))

    if permissions_all and not permissions_all.issubset(permission_set):
        return False

    has_any_entitlement_rule = bool(permissions_any or addon_keys_any or addon_functions_any)
    entitlement_match = False
    if permissions_any and not permission_set.isdisjoint(permissions_any):
        entitlement_match = True
    if addon_keys_any and not addon_key_set.isdisjoint(addon_keys_any):
        entitlement_match = True
    if addon_functions_any and not addon_function_set.isdisjoint(addon_functions_any):
        entitlement_match = True
    if has_any_entitlement_rule and not entitlement_match:
        return False

    min_user_limit = coerce_int(row_spec.get("min_user_limit"))
    if min_user_limit is not None:
        user_limit = coerce_int(limits.get("user_limit"))
        if user_limit is None:
            return False
        if user_limit != -1 and user_limit < min_user_limit:
            return False

    return True


# --- Build comparison cell ---
# Purpose: Produce typed cell payloads used by table renderers.
# Inputs: Tier fact dictionary and declarative row specification dictionary.
# Outputs: Cell dictionary containing type/value/display fields for the row.
def build_comparison_cell(*, tier: dict[str, Any], row_spec: dict[str, Any]) -> dict[str, Any]:
    """Build one display cell payload for a row/tier pair."""
    kind = str(row_spec.get("kind") or "boolean").strip().lower()
    if kind == "text":
        return {"type": "text", "display": str(row_spec.get("text") or "")}
    if kind == "limit":
        return {"type": "text", "display": format_limit_cell(tier=tier, row_spec=row_spec)}
    if kind == "batchbot_limit":
        return {"type": "text", "display": format_batchbot_limit_cell(tier)}
    if kind == "retention":
        return {
            "type": "text",
            "display": format_retention_cell(
                has_retention_entitlement=bool(tier.get("has_retention_entitlement")),
                retention_label=tier.get("retention_label"),
                retention_policy=tier.get("retention_policy"),
            ),
        }

    enabled = tier_matches_row_spec(tier=tier, row_spec=row_spec)
    return {
        "type": "boolean",
        "value": enabled,
        "display": "Included" if enabled else "Not included",
    }


# --- Format limit cell ---
# Purpose: Render a tier-specific limit row using row field metadata.
# Inputs: Tier fact dictionary and limit-row specification dictionary.
# Outputs: Customer-facing limit copy for one table cell.
def format_limit_cell(*, tier: dict[str, Any], row_spec: dict[str, Any]) -> str:
    """Render a limit row for one tier."""
    if not tier_matches_row_spec(tier=tier, row_spec=row_spec):
        return "Not included"

    limits = tier.get("limits") or {}
    limit_field = str(row_spec.get("limit_field") or "").strip()
    fallback_field = str(row_spec.get("fallback_field") or "").strip()
    raw_limit = coerce_int(limits.get(limit_field))
    if raw_limit is None and fallback_field:
        raw_limit = coerce_int(limits.get(fallback_field))

    none_display = str(row_spec.get("none_display") or "Unlimited")
    singular = str(row_spec.get("singular") or "item")
    plural = str(row_spec.get("plural") or f"{singular}s")
    return format_numeric_limit(
        value=raw_limit,
        singular=singular,
        plural=plural,
        none_display=none_display,
    )


# --- Format BatchBot limit cell ---
# Purpose: Render BatchBot access + request-cap copy for one tier.
# Inputs: Tier fact dictionary with entitlements and max_batchbot_requests limit.
# Outputs: Display string describing BatchBot availability/capacity.
def format_batchbot_limit_cell(tier: dict[str, Any]) -> str:
    """Render BatchBot request capacity copy for one tier."""
    has_access = tier_matches_row_spec(
        tier=tier,
        row_spec={
            "permissions_any": ("ai.batchbot",),
            "addon_keys_any": ("batchbot_access",),
        },
    )
    if not has_access:
        return "No assistant access"

    raw_limit = coerce_int((tier.get("limits") or {}).get("max_batchbot_requests"))
    if raw_limit is None:
        return "Contact support"
    if raw_limit < 0:
        return "Unlimited"
    if raw_limit == 0:
        return "No included requests"
    return f"{raw_limit} / window"

