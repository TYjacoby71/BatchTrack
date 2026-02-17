"""Inventory quantity-tracking policy helpers.

Synopsis:
Centralizes org-tier checks that decide whether on-hand inventory quantities
are decremented during deductions.

Glossary:
- Quantity tracking: Deductions reduce on-hand inventory quantities.
- Infinite mode: Deductions are logged without changing on-hand quantities.
"""

from __future__ import annotations

from app.utils.permissions import has_tier_permission


# --- Resolve quantity-tracking entitlement ---
# Purpose: Determine whether an organization tier allows tracked quantity deductions.
# Inputs: Optional organization model instance for explicit scoping.
# Outputs: True when quantity tracking is enabled for the effective organization tier.
def org_allows_inventory_quantity_tracking(*, organization=None) -> bool:
    """Return True when the org tier allows tracked quantity deductions."""
    return has_tier_permission(
        "inventory.track_quantities",
        organization=organization,
        default_if_missing_catalog=False,
    )
