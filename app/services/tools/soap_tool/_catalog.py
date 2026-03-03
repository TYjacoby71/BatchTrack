"""Soap bulk-oils catalog service helpers.

Synopsis:
Builds, caches, filters, and pages the soap bulk-oils catalog so routes stay
thin while global and CSV catalog sources are merged consistently.

Glossary:
- Bulk catalog: Oils records used by the Stage 2 bulk picker modal.
"""

from __future__ import annotations
import logging

import copy
from functools import lru_cache
from typing import Any

from flask import current_app
from sqlalchemy.orm import selectinload

from app.extensions import cache
from app.models import GlobalItem, IngredientDefinition
from app.services.cache_invalidation import global_library_cache_key
from app.services.soapcalc_catalog_data_service import (
    SOAPCALC_FATTY_KEYS,
    load_soapcalc_catalog_rows,
    parse_soapcalc_aliases,
    parse_soapcalc_float,
)
from app.utils.cache_utils import stable_cache_key

logger = logging.getLogger(__name__)


SOAP_BULK_FATTY_KEYS = SOAPCALC_FATTY_KEYS
SOAP_BULK_SORT_KEYS = {"name", *SOAP_BULK_FATTY_KEYS}
SOAP_BULK_PAGE_DEFAULT = 25
SOAP_BULK_PAGE_MAX = 25
SOAP_BULK_CATALOG_CACHE_TTL_SECONDS = 900
SOAP_BULK_PAGE_CACHE_TTL_SECONDS = 180
SOAP_BULK_ALLOWED_CATEGORIES = {
    "oils (carrier & fixed)",
    "butters & solid fats",
    "waxes",
}


# --- Soap bulk integer parser ---
# Purpose: Parse integer-like request input safely with fallback defaults.
# Inputs: Raw request value and integer fallback.
# Outputs: Parsed integer or fallback on parse failure.
def _to_int(raw_value: Any, fallback: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return fallback


# --- Soap catalog numeric parser ---
# Purpose: Parse soap CSV/global numeric fields including ranges and plus suffixes.
# Inputs: Raw value from CSV/database payload.
# Outputs: Float value when parseable, otherwise None.
def _parse_soap_catalog_float(raw: Any) -> float | None:
    return parse_soapcalc_float(raw)


# --- Soap catalog aliases parser ---
# Purpose: Normalize alias payloads into clean alias arrays.
# Inputs: Raw alias value from CSV/global payload.
# Outputs: List of alias strings.
def _parse_soap_catalog_aliases(raw: Any) -> list[str]:
    return parse_soapcalc_aliases(raw)


# --- Soap catalog fatty-profile normalizer ---
# Purpose: Normalize fatty-acid payloads into key-limited float mappings.
# Inputs: Fatty profile dictionary-like payload.
# Outputs: Dict of fatty keys to float values.
def _normalize_soap_catalog_fatty_profile(raw_profile: Any) -> dict[str, float]:
    if not isinstance(raw_profile, dict):
        return {}
    profile: dict[str, float] = {}
    for key in SOAP_BULK_FATTY_KEYS:
        value = _parse_soap_catalog_float(raw_profile.get(key))
        if value is not None:
            profile[key] = value
    return profile


# --- Soapcalc catalog loader ---
# Purpose: Load base soapcalc oils catalog from CSV for bulk-pick basics mode.
# Inputs: None.
# Outputs: List of normalized soap catalog records.
@lru_cache(maxsize=1)
def _load_soapcalc_catalog_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in load_soapcalc_catalog_rows():
        name = (row.get("name") or "").strip()
        if not name:
            continue
        category_name = (
            row.get("ingredient_category_name") or ""
        ).strip() or "Oils (Carrier & Fixed)"
        records.append(
            {
                "key": f"soapcalc:{name.lower()}",
                "name": name,
                "aliases": _parse_soap_catalog_aliases(row.get("aliases")),
                "sap_koh": _parse_soap_catalog_float(row.get("sap_koh")),
                "iodine": _parse_soap_catalog_float(row.get("iodine")),
                "fatty_profile": _normalize_soap_catalog_fatty_profile(
                    row.get("fatty_profile")
                ),
                "default_unit": (row.get("default_unit") or "").strip() or "gram",
                "ingredient_category_name": category_name,
                "global_item_id": None,
                "source": "soapcalc",
                "is_basic": True,
            }
        )
    return records


# --- Global oils catalog loader ---
# Purpose: Build oils/butters/waxes records from global item library.
# Inputs: SQLAlchemy global item table rows.
# Outputs: List of normalized global catalog records for bulk-pick all mode.
def _load_global_oil_catalog_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    items = (
        GlobalItem.query.options(
            selectinload(GlobalItem.ingredient).selectinload(
                IngredientDefinition.category
            ),
            selectinload(GlobalItem.ingredient_category),
        )
        .filter(GlobalItem.item_type == "ingredient")
        .filter(GlobalItem.is_archived.is_(False))
        .order_by(GlobalItem.name.asc())
        .all()
    )
    for gi in items:
        name = (gi.name or "").strip()
        if not name:
            continue
        ingredient_obj = getattr(gi, "ingredient", None)
        ingredient_category_obj = (
            ingredient_obj.category
            if ingredient_obj and getattr(ingredient_obj, "category", None)
            else getattr(gi, "ingredient_category", None)
        )
        category_name = (
            ingredient_category_obj.name if ingredient_category_obj else ""
        ) or ""
        if category_name.strip().lower() not in SOAP_BULK_ALLOWED_CATEGORIES:
            continue
        records.append(
            {
                "key": f"global:{gi.id}",
                "name": name,
                "aliases": _parse_soap_catalog_aliases(getattr(gi, "aliases", None)),
                "sap_koh": _parse_soap_catalog_float(
                    getattr(gi, "saponification_value", None)
                ),
                "iodine": _parse_soap_catalog_float(getattr(gi, "iodine_value", None)),
                "fatty_profile": _normalize_soap_catalog_fatty_profile(
                    getattr(gi, "fatty_acid_profile", None)
                ),
                "default_unit": (getattr(gi, "default_unit", None) or "gram"),
                "ingredient_category_name": category_name or "Oils (Carrier & Fixed)",
                "global_item_id": gi.id,
                "source": "global",
                "is_basic": False,
            }
        )
    return records


# --- Soap bulk mode normalizer ---
# Purpose: Normalize requested catalog mode to accepted values only.
# Inputs: Raw mode token from request.
# Outputs: Normalized mode string (basics|all).
def normalize_bulk_mode(raw_mode: str | None) -> str:
    return "all" if (raw_mode or "").strip().lower() == "all" else "basics"


# --- Soap bulk catalog merger ---
# Purpose: Build basics/all catalog with deterministic dedupe and ordering.
# Inputs: Normalized mode token.
# Outputs: List of merged catalog records for paging.
def _build_soap_bulk_catalog_uncached(mode: str) -> list[dict[str, Any]]:
    basics = [dict(row) for row in _load_soapcalc_catalog_records()]
    if mode != "all":
        return sorted(basics, key=lambda row: (row.get("name") or "").lower())

    merged: dict[str, dict[str, Any]] = {}
    for row in basics:
        dedupe_key = (row.get("name") or "").strip().lower()
        if dedupe_key:
            merged[dedupe_key] = row

    for row in _load_global_oil_catalog_records():
        dedupe_key = (row.get("name") or "").strip().lower()
        if not dedupe_key:
            continue
        existing = merged.get(dedupe_key)
        if not existing:
            merged[dedupe_key] = row
            continue
        if not existing.get("global_item_id") and row.get("global_item_id"):
            existing["global_item_id"] = row.get("global_item_id")
            existing["key"] = row.get("key")
        if not existing.get("sap_koh") and row.get("sap_koh"):
            existing["sap_koh"] = row.get("sap_koh")
        if not existing.get("iodine") and row.get("iodine"):
            existing["iodine"] = row.get("iodine")
        existing_fatty = existing.get("fatty_profile") or {}
        global_fatty = row.get("fatty_profile") or {}
        for key in SOAP_BULK_FATTY_KEYS:
            if key not in existing_fatty and key in global_fatty:
                existing_fatty[key] = global_fatty[key]
        existing["fatty_profile"] = existing_fatty
        existing_aliases = set(existing.get("aliases") or [])
        existing_aliases.update(row.get("aliases") or [])
        existing["aliases"] = sorted(existing_aliases)

    return sorted(merged.values(), key=lambda row: (row.get("name") or "").lower())


# --- Soap bulk cache timeout resolver ---
# Purpose: Resolve safe cache TTL values for bulk-catalog payload caching.
# Inputs: Flask config key and fallback TTL.
# Outputs: Positive integer timeout value in seconds.
def _soap_bulk_cache_timeout(config_key: str, fallback: int) -> int:
    configured = current_app.config.get(config_key, fallback)
    timeout = _to_int(configured, fallback)
    return max(30, timeout)


# --- Soap bulk cache-key builder ---
# Purpose: Build versioned cache keys linked to global-library cache namespace.
# Inputs: Key namespace and stable payload dimensions.
# Outputs: Versioned cache key string.
def _soap_bulk_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    return global_library_cache_key(stable_cache_key(namespace, payload))


# --- Soap bulk catalog cache wrapper ---
# Purpose: Reuse merged catalog payloads for hot modal traffic.
# Inputs: Mode token and optional bypass flag.
# Outputs: Catalog rows ready for page/filter operations.
def build_bulk_catalog(
    mode: str, *, bypass_cache: bool = False
) -> list[dict[str, Any]]:
    normalized_mode = normalize_bulk_mode(mode)
    if bypass_cache or not cache:
        return _build_soap_bulk_catalog_uncached(normalized_mode)

    cache_key = _soap_bulk_cache_key(
        "tools-soap-bulk-catalog",
        {"mode": normalized_mode},
    )
    try:
        cached_records = cache.get(cache_key)
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/tools/soap_tool/_catalog.py:261", exc_info=True)
        cached_records = None
    if isinstance(cached_records, list):
        return copy.deepcopy(cached_records)

    records = _build_soap_bulk_catalog_uncached(normalized_mode)
    try:
        cache.set(
            cache_key,
            records,
            timeout=_soap_bulk_cache_timeout(
                "TOOLS_SOAP_BULK_CATALOG_CACHE_TTL",
                SOAP_BULK_CATALOG_CACHE_TTL_SECONDS,
            ),
        )
    except Exception:
        logger.warning("Suppressed exception fallback at app/services/tools/soap_tool/_catalog.py:276", exc_info=True)
        pass
    return records


# --- Soap bulk sort-key normalizer ---
# Purpose: Normalize and validate requested sort key.
# Inputs: Raw sort key string.
# Outputs: Safe sort key accepted by backend sorter.
def normalize_bulk_sort_key(raw_sort_key: str | None) -> str:
    sort_key = (raw_sort_key or "name").strip().lower()
    if sort_key not in SOAP_BULK_SORT_KEYS:
        return "name"
    return sort_key


# --- Soap bulk record serializer ---
# Purpose: Strip non-display fields before returning catalog records to browser.
# Inputs: Normalized in-memory catalog record.
# Outputs: Compact JSON-safe record for modal rendering.
def serialize_bulk_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": record.get("key"),
        "name": record.get("name"),
        "sap_koh": record.get("sap_koh"),
        "iodine": record.get("iodine"),
        "fatty_profile": record.get("fatty_profile") or {},
        "default_unit": record.get("default_unit") or "gram",
        "ingredient_category_name": record.get("ingredient_category_name")
        or "Oils (Carrier & Fixed)",
        "global_item_id": record.get("global_item_id"),
        "source": record.get("source") or "soapcalc",
        "is_basic": bool(record.get("is_basic")),
    }


# --- Soap bulk catalog pager ---
# Purpose: Apply search/sort/pagination to bulk-catalog rows.
# Inputs: Full mode catalog list and page query options.
# Outputs: Tuple of paged records and total filtered count.
def page_bulk_catalog(
    *,
    records: list[dict[str, Any]],
    query: str,
    sort_key: str,
    sort_dir: str,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    normalized_query = (query or "").strip().lower()
    query_terms = [term for term in normalized_query.split() if term]
    if query_terms:

        def _matches_query(record: dict[str, Any]) -> bool:
            blob = " ".join(
                [
                    str(record.get("name") or ""),
                    " ".join(record.get("aliases") or []),
                    str(record.get("ingredient_category_name") or ""),
                ]
            ).lower()
            return all(term in blob for term in query_terms)

        filtered = [row for row in records if _matches_query(row)]
    else:
        filtered = list(records)

    normalized_sort_key = normalize_bulk_sort_key(sort_key)
    normalized_sort_dir = (
        "desc" if (sort_dir or "").strip().lower() == "desc" else "asc"
    )
    reverse = normalized_sort_dir == "desc"
    if normalized_sort_key == "name":
        filtered.sort(
            key=lambda row: str(row.get("name") or "").lower(), reverse=reverse
        )
    else:
        filtered.sort(
            key=lambda row: (
                float((row.get("fatty_profile") or {}).get(normalized_sort_key) or 0.0),
                str(row.get("name") or "").lower(),
            ),
            reverse=reverse,
        )

    total_count = len(filtered)
    safe_offset = max(0, _to_int(offset, 0))
    safe_limit = max(1, min(SOAP_BULK_PAGE_MAX, _to_int(limit, SOAP_BULK_PAGE_DEFAULT)))
    page_rows = filtered[safe_offset : safe_offset + safe_limit]
    return page_rows, total_count


# --- Soap bulk page result builder ---
# Purpose: Build full paged catalog API result with caching for hot paths.
# Inputs: Raw request values for mode/query/sort/page and cache bypass flag.
# Outputs: Structured result dictionary ready for JSON response payload.
def get_bulk_catalog_page(
    *,
    mode: str | None,
    query: str | None,
    sort_key: str | None,
    sort_dir: str | None,
    offset: int | str | None,
    limit: int | str | None,
    bypass_cache: bool = False,
) -> dict[str, Any]:
    normalized_mode = normalize_bulk_mode(mode)
    normalized_query = (query or "").strip()
    normalized_sort_key = normalize_bulk_sort_key(sort_key)
    normalized_sort_dir = (
        "desc" if (sort_dir or "").strip().lower() == "desc" else "asc"
    )
    safe_offset = max(0, _to_int(offset, 0))
    safe_limit = max(1, min(SOAP_BULK_PAGE_MAX, _to_int(limit, SOAP_BULK_PAGE_DEFAULT)))

    page_cache_key = _soap_bulk_cache_key(
        "tools-soap-bulk-page",
        {
            "mode": normalized_mode,
            "q": normalized_query,
            "sort_key": normalized_sort_key,
            "sort_dir": normalized_sort_dir,
            "offset": safe_offset,
            "limit": safe_limit,
        },
    )
    if not bypass_cache and cache:
        try:
            cached_result = cache.get(page_cache_key)
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/tools/soap_tool/_catalog.py:405", exc_info=True)
            cached_result = None
        if isinstance(cached_result, dict):
            return copy.deepcopy(cached_result)

    page_rows, total_count = page_bulk_catalog(
        records=build_bulk_catalog(normalized_mode, bypass_cache=bypass_cache),
        query=normalized_query,
        sort_key=normalized_sort_key,
        sort_dir=normalized_sort_dir,
        offset=safe_offset,
        limit=safe_limit,
    )
    next_offset = safe_offset + len(page_rows)
    result_payload = {
        "mode": normalized_mode,
        "query": normalized_query,
        "sort_key": normalized_sort_key,
        "sort_dir": normalized_sort_dir,
        "offset": safe_offset,
        "limit": safe_limit,
        "count": total_count,
        "next_offset": next_offset,
        "has_more": next_offset < total_count,
        "records": [serialize_bulk_record(row) for row in page_rows],
    }
    if not bypass_cache and cache:
        try:
            cache.set(
                page_cache_key,
                result_payload,
                timeout=_soap_bulk_cache_timeout(
                    "TOOLS_SOAP_BULK_PAGE_CACHE_TTL",
                    SOAP_BULK_PAGE_CACHE_TTL_SECONDS,
                ),
            )
        except Exception:
            logger.warning("Suppressed exception fallback at app/services/tools/soap_tool/_catalog.py:441", exc_info=True)
            pass
    return result_payload


__all__ = [
    "SOAP_BULK_FATTY_KEYS",
    "get_bulk_catalog_page",
    "normalize_bulk_sort_key",
    "page_bulk_catalog",
]
