"""Inventory lot/event code generation utilities.

Synopsis:
Generate and validate compact tracking identifiers for inventory events and
lot records using deterministic prefixes plus randomized base36 suffixes.

Glossary:
- Event prefix: Short code indicating the inventory change category.
- Lot code: Identifier prefixed with ``LOT`` for inventory lot tracking.
- Base36 suffix: Alphanumeric fragment derived from time, item id, and entropy.
"""

from __future__ import annotations

import secrets
import time
from typing import Dict, Literal, TypedDict

__all__ = [
    "generate_inventory_event_code",
    "parse_inventory_code",
    "validate_inventory_code",
    "int_to_base36",
]

BASE36_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOT_PREFIX = "LOT"
DEFAULT_EVENT_PREFIX = "EVT"

EVENT_PREFIXES: Dict[str, str] = {
    "recount": "RCN",
    "sale": "SLD",
    "use": "USE",
    "spoil": "SPL",
    "trash": "TRS",
    "expired": "EXP",
    "damaged": "DMG",
    "quality_fail": "QFL",
    "batch": "BCH",
    "sample": "SMP",
    "tester": "TST",
    "gift": "GFT",
    "returned": "RTN",
    "refunded": "REF",
    "cost_override": "CST",
}


# --- Parsed inventory code shape ---
# Purpose: Define structured keys returned by parse_inventory_code.
# Inputs: None.
# Outputs: Typed dictionary contract for parsed code payloads.
class ParsedCode(TypedDict):
    prefix: str | None
    suffix: str | None
    is_lot: bool
    code_type: Literal["lot", "event"] | None


# --- Integer to base36 ---
# Purpose: Encode positive integers using uppercase base36 characters.
# Inputs: Non-negative integer.
# Outputs: Base36 string representation.
def int_to_base36(num: int) -> str:
    if num == 0:
        return "0"

    digits = []
    while num:
        num, remainder = divmod(num, 36)
        digits.append(BASE36_CHARS[remainder])

    return "".join(reversed(digits))


# --- Generate code suffix ---
# Purpose: Build compact suffix using timestamp, item id, and random entropy.
# Inputs: Optional inventory item id for deterministic shard signal.
# Outputs: Uppercase six-character-ish composite suffix segment.
def _generate_suffix(item_id: int | None = None) -> str:
    timestamp_component = int_to_base36(int(time.time() * 1000)).rjust(6, "0")[-4:]
    item_component = int_to_base36(abs(item_id or 0)).rjust(3, "0")[-2:]
    random_component = int_to_base36(secrets.randbelow(36**3)).rjust(3, "0")[-2:]
    return f"{timestamp_component}{item_component}{random_component}".upper()


# --- Generate inventory event code ---
# Purpose: Produce lot/event tracking identifiers for inventory history.
# Inputs: Change type plus optional item id and requested code kind.
# Outputs: Hyphenated code string with validated prefix + generated suffix.
def generate_inventory_event_code(
    change_type: str,
    *,
    item_id: int | None = None,
    code_type: Literal["event", "lot"] = "event",
) -> str:
    """
    Generate inventory tracking codes for events and lots with consistent semantics.
    """
    if code_type == "lot":
        prefix = LOT_PREFIX
    else:
        normalized = (change_type or "").strip().lower()
        prefix = EVENT_PREFIXES.get(normalized, DEFAULT_EVENT_PREFIX)

    return f"{prefix}-{_generate_suffix(item_id)}"


# --- Parse inventory code ---
# Purpose: Split and classify tracking codes into structured components.
# Inputs: Candidate code string.
# Outputs: ParsedCode dictionary with prefix/suffix and code kind metadata.
def parse_inventory_code(code: str) -> ParsedCode:
    if not code or "-" not in code:
        return {"prefix": None, "suffix": None, "is_lot": False, "code_type": None}

    prefix, suffix = code.split("-", 1)
    is_lot = prefix == LOT_PREFIX
    return {
        "prefix": prefix,
        "suffix": suffix,
        "is_lot": is_lot,
        "code_type": "lot" if is_lot else "event",
    }


# --- Validate inventory code ---
# Purpose: Verify that code prefix belongs to supported lot/event prefixes.
# Inputs: Candidate inventory tracking code string.
# Outputs: Boolean validity indicator.
def validate_inventory_code(code: str) -> bool:
    parsed = parse_inventory_code(code)
    if not parsed["prefix"]:
        return False
    valid_prefixes = {LOT_PREFIX, DEFAULT_EVENT_PREFIX, *EVENT_PREFIXES.values()}
    return parsed["prefix"] in valid_prefixes
