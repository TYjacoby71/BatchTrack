"""Public tools routes.

Synopsis:
Defines public-facing maker tool pages and APIs, including soap calculator
execution and draft handoff into authenticated recipe creation.

Glossary:
- Tool draft: Session-backed payload captured from public tools for later save.
- Soap calculate API: Structured endpoint that delegates full stage computation
  to the soap tool service package.
"""

import copy
import csv
import os
import re
from functools import lru_cache
from typing import Any

from flask import Blueprint, render_template, request, jsonify, url_for, current_app
from flask_login import current_user
from sqlalchemy.orm import selectinload
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.services.tools.soap_tool import SoapToolComputationService
from app.models import GlobalItem, IngredientDefinition
from app.models import FeatureFlag
from app.extensions import limiter, cache
from app.services.cache_invalidation import global_library_cache_key
from app.utils.cache_utils import should_bypass_cache, stable_cache_key

# Public Tools blueprint
# Mounted at /tools via blueprints_registry

tools_bp = Blueprint('tools_bp', __name__)

SOAP_BULK_FATTY_KEYS = (
    "lauric",
    "myristic",
    "palmitic",
    "stearic",
    "ricinoleic",
    "oleic",
    "linoleic",
    "linolenic",
)
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
SOAP_BULK_RANGE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$")

# --- Feature-flag reader ---
# Purpose: Resolve tool enablement from persisted feature flags with fallback.
# Inputs: Feature key and optional default boolean.
# Outputs: Boolean flag value used by route rendering.
def _is_enabled(key: str, default: bool = True) -> bool:
    try:
        flag = FeatureFlag.query.filter_by(key=key).first()
        if flag is not None:
            return bool(flag.enabled)
        return default
    except Exception:
        return default


# --- Tool page renderer ---
# Purpose: Render a tool template with common public-header context.
# Inputs: Template path, feature-flag key, and extra context kwargs.
# Outputs: Flask rendered HTML response.
def _render_tool(template_name: str, flag_key: str, **context):
    enabled = _is_enabled(flag_key, True)
    return render_template(
        template_name,
        tool_enabled=enabled,
        show_public_header=True,
        **context,
    )


# --- Soap quota resolver ---
# Purpose: Determine per-day calc quota based on auth/tier context.
# Inputs: Current user/session organization state.
# Outputs: Tuple of (limit or None, tier label).
def _soap_calc_limit():
    if not getattr(current_user, "is_authenticated", False):
        return 5, "guest"
    org = getattr(current_user, "organization", None)
    tier = getattr(org, "tier", None) if org else None
    tier_name = (tier.name if tier else "") or ""
    if tier_name.lower().startswith("free"):
        return 5, "free"
    return None, tier_name or "paid"


# --- Soap quota consumer ---
# Purpose: Track and enforce rolling 24-hour draft quota for soap category.
# Inputs: Category name from payload and session storage state.
# Outputs: Quota result dict when quota applies, otherwise None.
def _consume_tool_quota(category_name: str | None):
    """Track draft submissions for free/guest tiers (daily rolling window)."""
    normalized = (category_name or "").strip().lower()
    if normalized != "soaps":
        return None
    limit, tier = _soap_calc_limit()
    if not limit:
        return None
    from flask import session
    from datetime import datetime, timezone, timedelta

    key = "soap_tool_quota"
    now = datetime.now(timezone.utc)
    record = session.get(key) or {}
    try:
        last_ts = record.get("timestamp")
        if last_ts:
            last_dt = datetime.fromisoformat(last_ts)
            if now - last_dt > timedelta(hours=24):
                record = {}
    except Exception:
        record = {}

    count = int(record.get("count") or 0)
    if count >= limit:
        return {"ok": False, "limit": limit, "tier": tier, "remaining": 0}

    count += 1
    record["count"] = count
    record["timestamp"] = now.isoformat()
    session[key] = record
    return {"ok": True, "limit": limit, "tier": tier, "remaining": max(0, limit - count)}


# --- Soap catalog numeric parser ---
# Purpose: Parse soap CSV numeric fields including ranges and plus suffix values.
# Inputs: Raw CSV value as string-like input.
# Outputs: Float value when parseable, otherwise None.
def _parse_soap_catalog_float(raw: Any) -> float | None:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered in {"low", "high", "n/a", "na"}:
        return None
    cleaned = cleaned.replace("+", "")
    range_match = SOAP_BULK_RANGE_RE.match(cleaned)
    if range_match:
        start = float(range_match.group(1))
        end = float(range_match.group(2))
        return (start + end) / 2.0
    try:
        return float(cleaned)
    except ValueError:
        return None


# --- Soap catalog aliases parser ---
# Purpose: Normalize comma/semicolon alias strings into clean alias arrays.
# Inputs: Raw aliases value from CSV/global payload.
# Outputs: List of alias strings.
def _parse_soap_catalog_aliases(raw: Any) -> list[str]:
    if not raw:
        return []
    aliases: list[str] = []
    if isinstance(raw, (list, tuple)):
        parts = [str(chunk) for chunk in raw]
    else:
        parts = re.split(r"[;,]", str(raw))
    for chunk in parts:
        cleaned = str(chunk).strip()
        if cleaned:
            aliases.append(cleaned)
    return aliases


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


# --- Soap CSV path resolver ---
# Purpose: Resolve absolute path to the canonical soapcalc catalog CSV file.
# Inputs: Flask app root path context.
# Outputs: Absolute filesystem path to catalog CSV.
def _soap_catalog_csv_path() -> str:
    primary = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "attached_assets", "soapcalc_tool_items.csv")
    )
    if os.path.exists(primary):
        return primary
    return os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            os.pardir,
            os.pardir,
            "data_builder",
            "ingredients",
            "data_sources",
            "soapcalc_oils_enrichment.csv",
        )
    )


# --- Soapcalc catalog loader ---
# Purpose: Load base soapcalc oils catalog from CSV for bulk-pick basics mode.
# Inputs: None.
# Outputs: List of normalized soap catalog records.
@lru_cache(maxsize=1)
def _load_soapcalc_catalog_records() -> list[dict[str, Any]]:
    path = _soap_catalog_csv_path()
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
            for key in SOAP_BULK_FATTY_KEYS:
                value = _parse_soap_catalog_float(row.get(key))
                if value is not None:
                    fatty_profile[key] = value
            category_name = (row.get("ingredient_category_name") or "").strip() or "Oils (Carrier & Fixed)"
            records.append(
                {
                    "key": f"soapcalc:{name.lower()}",
                    "name": name,
                    "aliases": _parse_soap_catalog_aliases(row.get("aliases")),
                    "sap_koh": _parse_soap_catalog_float(row.get("sap_koh")),
                    "iodine": _parse_soap_catalog_float(row.get("iodine")),
                    "fatty_profile": fatty_profile,
                    "default_unit": (row.get("default_unit") or "").strip() or "gram",
                    "ingredient_category_name": category_name,
                    "global_item_id": None,
                    "source": "soapcalc",
                    "is_basic": True,
                }
            )
    return records


# --- Global oils catalog loader ---
# Purpose: Build oils/butters/waxes records from the global item library.
# Inputs: SQLAlchemy global-item tables.
# Outputs: List of normalized global catalog records for bulk-pick all mode.
def _load_global_oil_catalog_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    items = (
        GlobalItem.query
        .options(
            selectinload(GlobalItem.ingredient).selectinload(IngredientDefinition.category),
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
        category_name = (ingredient_category_obj.name if ingredient_category_obj else "") or ""
        if category_name.strip().lower() not in SOAP_BULK_ALLOWED_CATEGORIES:
            continue
        records.append(
            {
                "key": f"global:{gi.id}",
                "name": name,
                "aliases": _parse_soap_catalog_aliases(getattr(gi, "aliases", None)),
                "sap_koh": _parse_soap_catalog_float(getattr(gi, "saponification_value", None)),
                "iodine": _parse_soap_catalog_float(getattr(gi, "iodine_value", None)),
                "fatty_profile": _normalize_soap_catalog_fatty_profile(getattr(gi, "fatty_acid_profile", None)),
                "default_unit": (getattr(gi, "default_unit", None) or "gram"),
                "ingredient_category_name": category_name or "Oils (Carrier & Fixed)",
                "global_item_id": gi.id,
                "source": "global",
                "is_basic": False,
            }
        )
    return records


# --- Soap bulk catalog merger ---
# Purpose: Build basics/all catalog views with deterministic dedupe and ordering.
# Inputs: Display mode token from request.
# Outputs: List of catalog records for bulk-oil UI consumption.
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
# Purpose: Resolve safe cache TTL values for soap bulk catalog payloads.
# Inputs: Flask config key and fallback TTL.
# Outputs: Positive integer timeout in seconds.
def _soap_bulk_cache_timeout(config_key: str, fallback: int) -> int:
    configured = current_app.config.get(config_key, fallback)
    try:
        timeout = int(configured)
    except (TypeError, ValueError):
        timeout = fallback
    return max(30, timeout)


# --- Soap bulk cache-key builder ---
# Purpose: Build versioned cache keys invalidated by global-library namespace bumps.
# Inputs: Key namespace and stable payload dimensions.
# Outputs: Versioned cache key string suitable for Flask-Caching.
def _soap_bulk_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    return global_library_cache_key(stable_cache_key(namespace, payload))


# --- Soap bulk catalog cache wrapper ---
# Purpose: Reuse merged catalog payloads for hot modal traffic.
# Inputs: Mode token and optional bypass flag for forced refresh.
# Outputs: Catalog rows ready for paging/filtering.
def _build_soap_bulk_catalog(mode: str, *, bypass_cache: bool = False) -> list[dict[str, Any]]:
    normalized_mode = "all" if mode == "all" else "basics"
    if bypass_cache or not cache:
        return _build_soap_bulk_catalog_uncached(normalized_mode)

    cache_key = _soap_bulk_cache_key(
        "tools-soap-bulk-catalog",
        {"mode": normalized_mode},
    )
    try:
        cached_records = cache.get(cache_key)
    except Exception:
        cached_records = None
    if isinstance(cached_records, list):
        return copy.deepcopy(cached_records)

    records = _build_soap_bulk_catalog_uncached(normalized_mode)
    try:
        cache.set(
            cache_key,
            records,
            timeout=_soap_bulk_cache_timeout("TOOLS_SOAP_BULK_CATALOG_CACHE_TTL", SOAP_BULK_CATALOG_CACHE_TTL_SECONDS),
        )
    except Exception:
        pass
    return records


# --- Soap bulk sort-key normalizer ---
# Purpose: Normalize and validate requested sort key for bulk-catalog paging.
# Inputs: Requested sort key string.
# Outputs: Safe sort key accepted by backend sorter.
def _normalize_soap_bulk_sort_key(raw_sort_key: str | None) -> str:
    sort_key = (raw_sort_key or "name").strip().lower()
    if sort_key not in SOAP_BULK_SORT_KEYS:
        return "name"
    return sort_key


# --- Soap bulk record serializer ---
# Purpose: Strip non-display fields before sending catalog records to browser.
# Inputs: Normalized in-memory catalog record.
# Outputs: JSON-safe compact record for modal rendering.
def _serialize_soap_bulk_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": record.get("key"),
        "name": record.get("name"),
        "sap_koh": record.get("sap_koh"),
        "iodine": record.get("iodine"),
        "fatty_profile": record.get("fatty_profile") or {},
        "default_unit": record.get("default_unit") or "gram",
        "ingredient_category_name": record.get("ingredient_category_name") or "Oils (Carrier & Fixed)",
        "global_item_id": record.get("global_item_id"),
        "source": record.get("source") or "soapcalc",
        "is_basic": bool(record.get("is_basic")),
    }


# --- Soap bulk catalog pager ---
# Purpose: Apply search/sort/pagination to bulk-catalog rows for incremental fetch.
# Inputs: Full mode catalog list and request query options.
# Outputs: Tuple of paged records and total filtered count.
def _page_soap_bulk_catalog(
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

    normalized_sort_key = _normalize_soap_bulk_sort_key(sort_key)
    normalized_sort_dir = "desc" if (sort_dir or "").strip().lower() == "desc" else "asc"
    reverse = normalized_sort_dir == "desc"
    if normalized_sort_key == "name":
        filtered.sort(key=lambda row: (str(row.get("name") or "").lower()), reverse=reverse)
    else:
        filtered.sort(
            key=lambda row: (
                float((row.get("fatty_profile") or {}).get(normalized_sort_key) or 0.0),
                str(row.get("name") or "").lower(),
            ),
            reverse=reverse,
        )

    total_count = len(filtered)
    safe_offset = max(0, int(offset or 0))
    safe_limit = max(1, min(SOAP_BULK_PAGE_MAX, int(limit or SOAP_BULK_PAGE_DEFAULT)))
    page_rows = filtered[safe_offset:safe_offset + safe_limit]
    return page_rows, total_count


# --- Tools landing route ---
# Purpose: Render public tools index with per-tool feature visibility flags.
# Inputs: HTTP request context and feature flag table.
# Outputs: Public tools index HTML response.
@tools_bp.route('/')
@limiter.limit("60000/hour;5000/minute")
def tools_index():
    """Public tools landing. Embeds calculators with progressive disclosure.
    Includes: Unit Converter, Fragrance Load Calculator, Lye Calculator (view-only),
    and quick draft Recipe Tool (category-aware) with Save CTA that invites sign-in.
    """
    flags = {
        'soap': _is_enabled('TOOLS_SOAP', True),
        'candles': _is_enabled('TOOLS_CANDLES', True),
        'lotions': _is_enabled('TOOLS_LOTIONS', True),
        'herbal': _is_enabled('TOOLS_HERBAL', True),
        'baker': _is_enabled('TOOLS_BAKING', True),
    }
    return render_template(
        'tools/index.html',
        tool_flags=flags,
        show_public_header=True,
    )


# --- Soap tool route ---
# Purpose: Render the soap formulator page with quota tier context.
# Inputs: HTTP request/user context.
# Outputs: Soap tool HTML response.
@tools_bp.route('/soap')
def tools_soap():
    calc_limit, calc_tier = _soap_calc_limit()
    return _render_tool('tools/soaps/index.html', 'TOOLS_SOAP', calc_limit=calc_limit, calc_tier=calc_tier)


# --- Candles tool route ---
# Purpose: Render public candles tool page.
# Inputs: HTTP request context.
# Outputs: Candles tool HTML response.
@tools_bp.route('/candles')
def tools_candles():
    return _render_tool('tools/candles.html', 'TOOLS_CANDLES')


# --- Lotions tool route ---
# Purpose: Render public lotions tool page.
# Inputs: HTTP request context.
# Outputs: Lotions tool HTML response.
@tools_bp.route('/lotions')
def tools_lotions():
    return _render_tool('tools/lotions.html', 'TOOLS_LOTIONS')


# --- Herbal tool route ---
# Purpose: Render public herbal tool page.
# Inputs: HTTP request context.
# Outputs: Herbal tool HTML response.
@tools_bp.route('/herbal')
def tools_herbal():
    return _render_tool('tools/herbal.html', 'TOOLS_HERBAL')


# --- Baker tool route ---
# Purpose: Render public baker tool page.
# Inputs: HTTP request context.
# Outputs: Baker tool HTML response.
@tools_bp.route('/baker')
def tools_baker():
    return _render_tool('tools/baker.html', 'TOOLS_BAKING')


# --- Soap calculate API route ---
# Purpose: Execute soap lye/water calculation through service package.
# Inputs: JSON payload with oils/lye/water inputs.
# Outputs: JSON success response with structured calculation result.
@tools_bp.route('/api/soap/calculate', methods=['POST'])
@limiter.limit("60000/hour;5000/minute")
def tools_soap_calculate():
    """Calculate soap stage outputs through structured service package."""
    payload = request.get_json(silent=True) or {}
    result = SoapToolComputationService.calculate(payload)
    return jsonify({"success": True, "result": result})


# --- Soap bulk-oils catalog API route ---
# Purpose: Return paged oils/butters/waxes catalog rows for bulk-oil picker modal.
# Inputs: Query params mode/q/sort/offset/limit for server-side paging/search.
# Outputs: JSON payload with normalized paged records and cursor metadata.
@tools_bp.route('/api/soap/oils-catalog', methods=['GET'])
@limiter.limit("1200/hour;120/minute")
def tools_soap_oils_catalog():
    mode = (request.args.get("mode") or "basics").strip().lower()
    if mode not in {"basics", "all"}:
        mode = "basics"
    query = (request.args.get("q") or "").strip()
    sort_key = _normalize_soap_bulk_sort_key(request.args.get("sort_key"))
    sort_dir = (request.args.get("sort_dir") or "asc").strip().lower()
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "asc"
    try:
        offset = max(0, int(request.args.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = max(1, min(SOAP_BULK_PAGE_MAX, int(request.args.get("limit") or SOAP_BULK_PAGE_DEFAULT)))
    except (TypeError, ValueError):
        limit = SOAP_BULK_PAGE_DEFAULT
    bypass_cache = should_bypass_cache()
    page_cache_key = _soap_bulk_cache_key(
        "tools-soap-bulk-page",
        {
            "mode": mode,
            "q": query,
            "sort_key": sort_key,
            "sort_dir": sort_dir,
            "offset": offset,
            "limit": limit,
        },
    )
    if not bypass_cache and cache:
        try:
            cached_result = cache.get(page_cache_key)
        except Exception:
            cached_result = None
        if isinstance(cached_result, dict):
            return jsonify({"success": True, "result": cached_result})

    page_rows, total_count = _page_soap_bulk_catalog(
        records=_build_soap_bulk_catalog(mode, bypass_cache=bypass_cache),
        query=query,
        sort_key=sort_key,
        sort_dir=sort_dir,
        offset=offset,
        limit=limit,
    )
    next_offset = offset + len(page_rows)
    has_more = next_offset < total_count
    result_payload = {
        "mode": mode,
        "query": query,
        "sort_key": sort_key,
        "sort_dir": sort_dir,
        "offset": offset,
        "limit": limit,
        "count": total_count,
        "next_offset": next_offset,
        "has_more": has_more,
        "records": [_serialize_soap_bulk_record(row) for row in page_rows],
    }
    if not bypass_cache and cache:
        try:
            cache.set(
                page_cache_key,
                result_payload,
                timeout=_soap_bulk_cache_timeout("TOOLS_SOAP_BULK_PAGE_CACHE_TTL", SOAP_BULK_PAGE_CACHE_TTL_SECONDS),
            )
        except Exception:
            pass
    return jsonify({"success": True, "result": result_payload})


# --- Public draft capture route ---
# Purpose: Persist public tool draft payload into session for auth handoff.
# Inputs: JSON draft payload with optional recipe lines.
# Outputs: JSON response with redirect target or quota error.
@tools_bp.route('/draft', methods=['POST'])
def tools_draft():
    """Accept a draft from the public tools page and redirect to sign-in/save flow.
    The draft payload is stored in session via query string for now (MVP), then the
    /recipes/new page will read and prefill when user is authenticated.
    """
    from flask import session
    data = request.get_json() or {}
    quota = _consume_tool_quota(data.get("category_name"))
    if quota and not quota.get("ok"):
        msg = (
            f"Free tools allow {quota['limit']} submissions per day. "
            "Create a free account or upgrade to keep saving drafts."
        )
        return jsonify({"success": False, "error": msg, "limit_reached": True}), 429
    # Normalize line arrays if provided
    def _norm_lines(lines, kind):
        out = []
        for ln in (lines or []):
            try:
                name = (ln.get('name') or '').strip() or None
                gi = ln.get('global_item_id')
                gi = int(gi) if gi not in (None, '', []) else None
                qty = ln.get('quantity')
                try:
                    qty = float(qty) if qty not in (None, '', []) else None
                except Exception:
                    qty = None
                unit = (ln.get('unit') or '').strip() or None
                rec = {
                    'name': name,
                    'global_item_id': gi,
                    'default_unit': (ln.get('default_unit') or '').strip() or None,
                    'ingredient_category_name': (ln.get('ingredient_category_name') or '').strip() or None,
                }
                if kind == 'container':
                    rec['quantity'] = int(qty) if qty is not None else 1
                else:
                    rec['quantity'] = float(qty) if qty is not None else 0.0
                    rec['unit'] = unit or 'gram'
                out.append(rec)
            except Exception:
                continue
        return out

    if 'ingredients' in data:
        data['ingredients'] = _norm_lines(data.get('ingredients'), 'ingredient')
    if 'consumables' in data:
        data['consumables'] = _norm_lines(data.get('consumables'), 'consumable')
    if 'containers' in data:
        data['containers'] = _norm_lines(data.get('containers'), 'container')
    # Merge to preserve any prior progress and keep across redirects
    try:
        from datetime import datetime, timezone
        existing = session.get('tool_draft', {})
        if not isinstance(existing, dict):
            existing = {}
        existing.update(data or {})
        session['tool_draft'] = existing

        # Track draft metadata for TTL and debugging
        meta = session.get('tool_draft_meta') or {}
        if not isinstance(meta, dict):
            meta = {}
        if not meta.get('created_at'):
            meta['created_at'] = datetime.now(timezone.utc).isoformat()
        meta['last_updated_at'] = datetime.now(timezone.utc).isoformat()
        meta['source'] = 'public_tools'
        session['tool_draft_meta'] = meta

        # Do NOT make the entire session permanent just for a draft
        # Let session behave normally so drafts end with the browser session
        try:
            session.permanent = False
        except Exception:
            pass
    except Exception:
        session['tool_draft'] = data
        try:
            session.pop('tool_draft_meta', None)
        except Exception:
            pass
    # Redirect to sign-in or directly to recipes new if already logged in
    return jsonify({'success': True, 'redirect': url_for('recipes.new_recipe')})