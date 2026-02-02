import csv
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from flask import current_app

SOAPCALC_CATEGORY = "Oils (Carrier & Fixed)"
FATTY_KEYS = (
    "lauric",
    "myristic",
    "palmitic",
    "stearic",
    "ricinoleic",
    "oleic",
    "linoleic",
    "linolenic",
)
_RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$")


def _soapcalc_csv_path() -> str:
    return os.path.abspath(
        os.path.join(current_app.root_path, os.pardir, "attached_assets", "soapcalc_oils_enrichment.csv")
    )


def _parse_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered in {"low", "high"}:
        return None
    cleaned = cleaned.replace("+", "")
    match = _RANGE_RE.match(cleaned)
    if match:
        start = float(match.group(1))
        end = float(match.group(2))
        return (start + end) / 2
    try:
        return float(cleaned)
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _load_oil_records() -> List[Dict[str, Any]]:
    path = _soapcalc_csv_path()
    if not os.path.exists(path):
        current_app.logger.warning("Soapcalc oil enrichment CSV not found at %s", path)
        return []
    records: List[Dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("name") or "").strip()
            if not name:
                continue
            aliases = (row.get("aliases") or "").strip()
            saponification_value = _parse_float(row.get("sap_koh"))
            iodine_value = _parse_float(row.get("iodine"))
            fatty_profile: Dict[str, float] = {}
            for key in FATTY_KEYS:
                value = _parse_float(row.get(key))
                if value is not None:
                    fatty_profile[key] = value
            records.append(
                {
                    "name": name,
                    "aliases": aliases,
                    "search_blob": f"{name} {aliases}".strip().lower(),
                    "ingredient_category_name": SOAPCALC_CATEGORY,
                    "saponification_value": saponification_value,
                    "iodine_value": iodine_value,
                    "fatty_acid_profile": fatty_profile or None,
                }
            )
    return records


def _score_record(record: Dict[str, Any], query: str) -> tuple:
    name = (record.get("name") or "").lower()
    aliases = (record.get("aliases") or "").lower()
    if name == query:
        return (0, len(name))
    if name.startswith(query):
        return (1, len(name))
    if aliases.startswith(query) and aliases:
        return (2, len(aliases))
    name_pos = name.find(query)
    if name_pos >= 0:
        return (3, name_pos, len(name))
    alias_pos = aliases.find(query) if aliases else -1
    if alias_pos >= 0:
        return (4, alias_pos, len(aliases))
    return (5, len(name))


def _build_item_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    name = record.get("name")
    return {
        "id": None,
        "name": name,
        "text": name,
        "display_name": name,
        "item_type": "ingredient",
        "ingredient_category_name": record.get("ingredient_category_name"),
        "aliases": [record.get("aliases")] if record.get("aliases") else [],
        "saponification_value": record.get("saponification_value"),
        "iodine_value": record.get("iodine_value"),
        "fatty_acid_profile": record.get("fatty_acid_profile"),
    }


def _build_group_payload(record: Dict[str, Any]) -> Dict[str, Any]:
    name = record.get("name")
    category = record.get("ingredient_category_name")
    return {
        "id": None,
        "ingredient_id": None,
        "name": name,
        "text": name,
        "display_name": name,
        "item_type": "ingredient",
        "ingredient": {
            "id": None,
            "name": name,
            "ingredient_category_name": category,
        },
        "ingredient_category_name": category,
        "forms": [
            {
                "id": None,
                "name": name,
                "text": name,
                "display_name": name,
                "item_type": "ingredient",
                "ingredient_name": name,
                "ingredient_category_name": category,
                "aliases": [record.get("aliases")] if record.get("aliases") else [],
                "saponification_value": record.get("saponification_value"),
                "iodine_value": record.get("iodine_value"),
                "fatty_acid_profile": record.get("fatty_acid_profile"),
            }
        ],
    }


def search_soapcalc_oils(query: str, *, limit: int = 25, group: bool = False) -> List[Dict[str, Any]]:
    if not query:
        return []
    normalized = query.strip().lower()
    if not normalized:
        return []
    terms = [term for term in normalized.split() if term]
    records = [
        record
        for record in _load_oil_records()
        if all(term in record.get("search_blob", "") for term in terms)
    ]
    records.sort(key=lambda record: _score_record(record, normalized))
    if limit:
        records = records[:limit]
    if group:
        return [_build_group_payload(record) for record in records]
    return [_build_item_payload(record) for record in records]
