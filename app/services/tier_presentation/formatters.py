"""Formatting helpers for tier presentation cells.

Synopsis:
Converts raw limits and policy values into customer-facing copy.

Glossary:
- None display: String used when no numeric limit is available.
- Retention policy: Storage lifecycle mode for tier data.
"""

from __future__ import annotations


# --- Format numeric limit ---
# Purpose: Render count limits into customer-readable plan copy.
# Inputs: Numeric limit value and singular/plural/none display tokens.
# Outputs: Display string describing included quantity or entitlement status.
def format_numeric_limit(
    *,
    value: int | None,
    singular: str,
    plural: str,
    none_display: str,
) -> str:
    """Format numeric limits with standard plan-language conventions."""
    if value is None:
        return none_display
    if value < 0:
        return "Unlimited"
    if value == 0:
        return "Not included"
    if value == 1:
        return f"1 {singular}"
    return f"Up to {value} {plural}"


# --- Format retention cell ---
# Purpose: Convert retention entitlements/policy metadata into display text.
# Inputs: Retention entitlement flag plus optional label/policy values.
# Outputs: Human-readable retention policy string for table cells.
def format_retention_cell(
    *,
    has_retention_entitlement: bool,
    retention_label: str | None,
    retention_policy: str | None,
) -> str:
    """Return a human-readable retention policy string."""
    if has_retention_entitlement:
        return "Retained while subscribed"

    label = str(retention_label or "").strip()
    normalized_label = label.lower()
    if normalized_label in {"subscribed", "while subscribed", "retained while subscribed"}:
        return "Retained while subscribed"
    if normalized_label in {"1 year", "one year"}:
        return "1 year standard retention"
    if label:
        return label

    if str(retention_policy or "").strip().lower() == "subscribed":
        return "Retained while subscribed"
    return "1 year standard retention"

