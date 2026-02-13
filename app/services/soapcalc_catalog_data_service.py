"""Shared Soapcalc catalog CSV loader and normalizers.

Synopsis:
Provides one cached reader for soapcalc_source_verified.csv so multiple
consumers can reuse the same parsing and normalization logic.

Glossary:
- Soapcalc catalog rows: Canonical oil records loaded from the source CSV.
"""

from __future__ import annotations

import csv
import os
import re
from functools import lru_cache
from typing import Any

SOAPCALC_FATTY_KEYS = (
    "lauric",
    "myristic",
    "palmitic",
    "stearic",
    "ricinoleic",
    "oleic",
    "linoleic",
    "linolenic",
)
SOAPCALC_RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$")


# --- Soapcalc CSV path resolver ---
# Purpose: Resolve absolute path to canonical soapcalc source CSV.
# Inputs: None.
# Outputs: Absolute filesystem path string.
def soapcalc_csv_path() -> str:
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            os.pardir,
            "data_builder",
            "ingredients",
            "data_sources",
            "soapcalc_source_verified.csv",
        )
    )


# --- Soapcalc unit normalizer ---
# Purpose: Normalize common unit aliases to canonical unit strings.
# Inputs: Raw unit value from CSV.
# Outputs: Canonical unit token or None.
def normalize_soapcalc_unit(raw: Any) -> str | None:
    if not raw:
        return None
    cleaned = str(raw).strip().lower()
    if not cleaned:
        return None
    if cleaned in {"ml", "milliliter", "milliliters"}:
        return "milliliter"
    if cleaned in {"g", "gram", "grams"}:
        return "gram"
    return cleaned


# --- Soapcalc numeric parser ---
# Purpose: Parse numeric-like soapcalc fields with range support.
# Inputs: Raw CSV field value.
# Outputs: Float value or None when unparseable.
def parse_soapcalc_float(raw: Any) -> float | None:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered in {"low", "high", "n/a", "na"}:
        return None
    cleaned = cleaned.replace("+", "")
    range_match = SOAPCALC_RANGE_RE.match(cleaned)
    if range_match:
        start = float(range_match.group(1))
        end = float(range_match.group(2))
        return (start + end) / 2.0
    try:
        return float(cleaned)
    except ValueError:
        return None


# --- Soapcalc aliases parser ---
# Purpose: Normalize alias payloads from CSV fields into string arrays.
# Inputs: Raw aliases value.
# Outputs: List of cleaned alias strings.
def parse_soapcalc_aliases(raw: Any) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        parts = [str(chunk) for chunk in raw]
    else:
        parts = re.split(r"[;,]", str(raw))
    aliases: list[str] = []
    for chunk in parts:
        cleaned = str(chunk).strip()
        if cleaned:
            aliases.append(cleaned)
    return aliases


# --- Soapcalc catalog row loader ---
# Purpose: Load and normalize source CSV records for shared reuse.
# Inputs: None.
# Outputs: List of canonical soapcalc catalog row dictionaries.
@lru_cache(maxsize=1)
def load_soapcalc_catalog_rows() -> list[dict[str, Any]]:
    path = soapcalc_csv_path()
    if not os.path.exists(path):
        return []
    records: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            fatty_profile: dict[str, float] = {}
            for key in SOAPCALC_FATTY_KEYS:
                value = parse_soapcalc_float(row.get(key))
                if value is not None:
                    fatty_profile[key] = value
            records.append(
                {
                    "name": name,
                    "aliases": parse_soapcalc_aliases(row.get("aliases")),
                    "sap_koh": parse_soapcalc_float(row.get("sap_koh")),
                    "iodine": parse_soapcalc_float(row.get("iodine")),
                    "fatty_profile": fatty_profile,
                    "ingredient_category_name": (row.get("ingredient_category_name") or "").strip() or None,
                    "default_unit": normalize_soapcalc_unit(row.get("default_unit")),
                }
            )
    return records


__all__ = [
    "SOAPCALC_FATTY_KEYS",
    "load_soapcalc_catalog_rows",
    "normalize_soapcalc_unit",
    "parse_soapcalc_aliases",
    "parse_soapcalc_float",
    "soapcalc_csv_path",
]
