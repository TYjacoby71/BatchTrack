from __future__ import annotations

import secrets
import time
from typing import Dict, Literal, TypedDict

__all__ = [
    "generate_inventory_event_code",
    "generate_fifo_code",
    "parse_inventory_code",
    "parse_fifo_code",
    "validate_inventory_code",
    "validate_fifo_code",
    "generate_fifo_id",
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


class ParsedCode(TypedDict):
    prefix: str | None
    suffix: str | None
    is_lot: bool
    code_type: Literal["lot", "event"] | None


def _int_to_base36(num: int) -> str:
    if num == 0:
        return "0"

    digits = []
    while num:
        num, remainder = divmod(num, 36)
        digits.append(BASE36_CHARS[remainder])

    return "".join(reversed(digits))


def _generate_suffix(item_id: int | None = None) -> str:
    timestamp_component = _int_to_base36(int(time.time() * 1000)).rjust(6, "0")[-4:]
    item_component = _int_to_base36(abs(item_id or 0)).rjust(3, "0")[-2:]
    random_component = _int_to_base36(secrets.randbelow(36**3)).rjust(3, "0")[-2:]
    return f"{timestamp_component}{item_component}{random_component}".upper()


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


def generate_fifo_code(change_type, item_id=None, is_lot_creation=False):
    """
    Backwards-compatible wrapper that delegates to the new inventory code generator.
    """
    code_type: Literal["event", "lot"] = "lot" if is_lot_creation else "event"
    return generate_inventory_event_code(change_type, item_id=item_id, code_type=code_type)


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


def parse_fifo_code(fifo_code):
    """Legacy wrapper for parse_inventory_code."""
    return parse_inventory_code(fifo_code)


def validate_inventory_code(code: str) -> bool:
    parsed = parse_inventory_code(code)
    if not parsed["prefix"]:
        return False
    valid_prefixes = {LOT_PREFIX, DEFAULT_EVENT_PREFIX, *EVENT_PREFIXES.values()}
    return parsed["prefix"] in valid_prefixes


def validate_fifo_code(fifo_code):
    """Legacy wrapper for validate_inventory_code."""
    return validate_inventory_code(fifo_code)


def generate_fifo_id(change_type):
    """Legacy function - use generate_fifo_code instead"""
    return generate_fifo_code(change_type)