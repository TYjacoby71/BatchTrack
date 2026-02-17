from functools import lru_cache
from typing import Any, Optional

from app.services.soapcalc_catalog_data_service import (
    load_soapcalc_catalog_rows,
    normalize_soapcalc_unit,
)

DEFAULT_OIL_CATEGORY = "Oils (Carrier & Fixed)"
DEFAULT_BUTTER_CATEGORY = "Butters & Solid Fats"
DEFAULT_WAX_CATEGORY = "Waxes"
DEFAULT_UNIT_BY_CATEGORY = {
    "Oils (Carrier & Fixed)": "milliliter",
    "Essential Oils": "milliliter",
    "Fragrance Oils": "milliliter",
    "Butters & Solid Fats": "gram",
    "Waxes": "gram",
    "Sugars & Syrups": "gram",
    "Salts & Minerals": "gram",
    "Preservatives & Additives": "gram",
    "Aqueous Solutions & Blends": "milliliter",
}
WAX_KEYWORDS = ("wax",)
BUTTER_FAT_KEYWORDS = (
    "butter",
    "tallow",
    "lard",
    "shortening",
    "stearin",
    "stearic",
    "palmitic",
    "lauric",
    "myristic",
    "ricinoleic",
    "oleic acid",
    "milk fat",
    "ghee",
)


def _infer_category(name: str) -> str:
    lowered = (name or "").lower()
    if any(keyword in lowered for keyword in WAX_KEYWORDS):
        return DEFAULT_WAX_CATEGORY
    if any(keyword in lowered for keyword in BUTTER_FAT_KEYWORDS):
        return DEFAULT_BUTTER_CATEGORY
    return DEFAULT_OIL_CATEGORY


def _infer_default_unit(category: Optional[str]) -> str:
    if category and category in DEFAULT_UNIT_BY_CATEGORY:
        return DEFAULT_UNIT_BY_CATEGORY[category]
    return "gram"


@lru_cache(maxsize=1)
def _load_item_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in load_soapcalc_catalog_rows():
        name = (row.get("name") or "").strip()
        if not name:
            continue
        aliases = list(row.get("aliases") or [])
        category = (
            row.get("ingredient_category_name") or ""
        ).strip() or _infer_category(name)
        default_unit = normalize_soapcalc_unit(
            row.get("default_unit")
        ) or _infer_default_unit(category)
        records.append(
            {
                "name": name,
                "aliases": aliases,
                "search_blob": f"{name} {' '.join(aliases)}".strip().lower(),
                "ingredient_category_name": category,
                "default_unit": default_unit,
                "saponification_value": row.get("sap_koh"),
                "iodine_value": row.get("iodine"),
                "fatty_acid_profile": row.get("fatty_profile") or None,
            }
        )
    return records


def _score_record(record: dict[str, Any], query: str) -> tuple:
    name = (record.get("name") or "").lower()
    alias_list = record.get("aliases") or []
    aliases = " ".join(alias_list).lower()
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


def _build_item_payload(record: dict[str, Any]) -> dict[str, Any]:
    name = record.get("name")
    return {
        "id": None,
        "name": name,
        "text": name,
        "display_name": name,
        "item_type": "ingredient",
        "ingredient_category_name": record.get("ingredient_category_name"),
        "default_unit": record.get("default_unit"),
        "unit": record.get("default_unit"),
        "aliases": record.get("aliases") or [],
        "saponification_value": record.get("saponification_value"),
        "iodine_value": record.get("iodine_value"),
        "fatty_acid_profile": record.get("fatty_acid_profile"),
    }


def _build_group_payload(record: dict[str, Any]) -> dict[str, Any]:
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
                "default_unit": record.get("default_unit"),
                "unit": record.get("default_unit"),
                "aliases": record.get("aliases") or [],
                "saponification_value": record.get("saponification_value"),
                "iodine_value": record.get("iodine_value"),
                "fatty_acid_profile": record.get("fatty_acid_profile"),
            }
        ],
    }


def search_soapcalc_items(
    query: str, *, limit: int = 25, group: bool = False
) -> list[dict[str, Any]]:
    if not query:
        return []
    normalized = query.strip().lower()
    if not normalized:
        return []
    terms = [term for term in normalized.split() if term]
    records = [
        record
        for record in _load_item_records()
        if all(term in record.get("search_blob", "") for term in terms)
    ]
    records.sort(key=lambda record: _score_record(record, normalized))
    if limit:
        records = records[:limit]
    if group:
        return [_build_group_payload(record) for record in records]
    return [_build_item_payload(record) for record in records]


def search_soapcalc_oils(
    query: str, *, limit: int = 25, group: bool = False
) -> list[dict[str, Any]]:
    return search_soapcalc_items(query, limit=limit, group=group)
