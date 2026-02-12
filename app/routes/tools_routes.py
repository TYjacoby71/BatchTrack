"""Public tools routes.

Synopsis:
Defines public-facing maker tool pages and APIs, including soap calculator
execution and draft handoff into authenticated recipe creation.

Glossary:
- Tool draft: Session-backed payload captured from public tools for later save.
- Soap calculate API: Structured endpoint that delegates full stage computation
  to the soap tool service package.
"""

import csv
import os
import re
from functools import lru_cache
from typing import Any

from flask import Blueprint, render_template, request, jsonify, url_for
from flask_login import current_user
from app.services.unit_conversion.unit_conversion import ConversionEngine
from app.services.tools.soap_tool import SoapToolComputationService
from app.models import GlobalItem
from app.models import FeatureFlag
from app.extensions import limiter

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
        .filter(GlobalItem.item_type == "ingredient")
        .filter(GlobalItem.is_archived != True)
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
def _build_soap_bulk_catalog(mode: str) -> list[dict[str, Any]]:
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
# Purpose: Return oils/butters/waxes catalog for bulk-oil picker modal.
# Inputs: Query param mode=basics|all.
# Outputs: JSON payload with normalized catalog records.
@tools_bp.route('/api/soap/oils-catalog', methods=['GET'])
@limiter.limit("60000/hour;5000/minute")
def tools_soap_oils_catalog():
    mode = (request.args.get("mode") or "basics").strip().lower()
    if mode not in {"basics", "all"}:
        mode = "basics"
    records = _build_soap_bulk_catalog(mode)
    return jsonify(
        {
            "success": True,
            "result": {
                "mode": mode,
                "count": len(records),
                "records": records,
            },
        }
    )


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