"""OpenAI worker responsible for fetching structured ingredient data."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict

import openai

LOGGER = logging.getLogger(__name__)

from .taxonomy_constants import (
    INGREDIENT_CATEGORIES_PRIMARY,
    ORIGINS,
    PHYSICAL_FORMS,
    REFINEMENT_LEVELS,
    VARIATIONS_CURATED,
)

openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    LOGGER.warning("OPENAI_API_KEY is not set; ai_worker will fail until configured.")

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("AI_RETRY_BACKOFF", "3"))
MULTI_PROMPT_MODE = os.getenv("AI_WORKER_MULTI_PROMPT", "1").strip() not in {"0", "false", "False"}

try:  # pragma: no cover
    from . import sources
except Exception:  # pragma: no cover
    sources = None  # type: ignore

INGREDIENT_CATEGORIES = [
    "Aqueous Solutions & Blends", 
    "Botanicals (Dried)",
    "Butters (Solid Fats)",
    "Clays",
    "Colorants & Pigments",
    "Cultures, SCOBYs & Fermentation",
    "Essential Oils",
    "Extracts (Alcohols & Solvents)",
    "Flours & Powders (Organic)",
    "Fragrance Oils",
    "Fruits, Nuts & Seeds (Whole/Chopped)",
    "Herbs & Spices (Dried Botanicals)",
    "Hydrosols & Floral Waters",
    "Liquid Extracts (Aqueous/Glycerine)",
    "Liquids (Aqueous)",
    "Miscellaneous",
    "Oils (Carrier & Fixed)",
    "Polymers (Synthetic)",
    "Preservatives & Additives",
    "Resins (Natural)",
    "Salts & Minerals",
    "Starches & Thickeners",
    "Sugars & Syrups",
    "Surfactants & Emulsifiers",
    "Waxes"
]

SYSTEM_PROMPT = (
    "IngredientCompilerGPT. JSON only. Use training knowledge for common specs (SAP, iodine, density). "
    "\"N/A\"=not applicable. \"Not Found\"=truly unknown. All fields required."
)

JSON_SCHEMA_SPEC = r"""
{
  "ingredient": {
    "common_name": "string",
    "category": "ingredient category",
    "botanical_name": "string",
    "inci_name": "string",
    "cas_number": "string",
    "short_description": "string",
    "detailed_description": "string",
    "origin": {"regions": [], "source_material": "string", "processing_methods": []},
    "primary_functions": [],
    "regulatory_notes": [],
    "items": [{
      "item_name": "Name (Variation)",
      "variation": "string",
      "physical_form": "Oil|Liquid|Powder|Granules|Crystals|Whole|Butter|Wax|Resin|Gel|Paste",
      "synonyms": [],
      "applications": [],
      "function_tags": [],
      "safety_tags": [],
      "shelf_life_days": 30-3650,
      "sds_hazards": [],
      "storage": {"temperature_celsius": {"min": 5, "max": 25}, "humidity_percent": {"max": 60}, "special_instructions": "string"},
      "specifications": {"sap_naoh": 0.128, "sap_koh": 0.18, "iodine_value": 10, "melting_point_celsius": {"min": 30, "max": 35}, "flash_point_celsius": 200, "ph_range": {"min": 5, "max": 7}},
      "sourcing": {"common_origins": [], "certifications": [], "supply_risks": [], "sustainability_notes": "string"},
      "form_bypass": false,
      "variation_bypass": false
    }],
    "taxonomy": {"scent_profile": [], "color_profile": [], "texture_profile": [], "compatible_processes": [], "incompatible_processes": []},
    "documentation": {"references": [], "last_verified": "ISO-8601 date"}
  },
  "data_quality": {"confidence": 0-1, "caveats": []}
}
"""

ERROR_OBJECT = {"error": "Unable to return ingredient payload"}

PROMPT_TEMPLATE = """
TASK: Build ingredient dossier for: "{ingredient}".

RULES:
- RAW INGREDIENTS ONLY (no packaging/containers)
- Create items for each purchasable variation/form
- Unknown="Not Found", Not applicable="N/A"
- Metric units, shelf_life in DAYS, temp in Celsius
- variation=processing type (Refined, Cold Pressed, Essential Oil)
- physical_form=state noun (Oil, Liquid, Powder, Butter, Wax)
- Categories: {categories}

SCHEMA:
{schema}

Return valid JSON. If out of scope: {error_object}
"""

CORE_SCHEMA_SPEC = r"""
{
  "ingredient_core": {
    "origin": "Plant-Derived|Animal-Derived|Animal-Byproduct|Mineral/Earth|Synthetic|Fermentation|Marine-Derived",
    "ingredient_category": "Fruits|Vegetables|Grains|Nuts|Seeds|Spices|Herbs|Flowers|Roots|Barks|Clays|Minerals|Salts|Sugars",
    "refinement_level": "Raw/Unprocessed|Minimally Processed|Extracted/Distilled|Milled/Ground|Fermented|Synthesized",
    "derived_from": "string",
    "category": "ingredient category",
    "botanical_name": "Latin binomial",
    "inci_name": "INCI name",
    "cas_number": "CAS number",
    "short_description": "string",
    "detailed_description": "string",
    "usage_restrictions": "string",
    "prohibited_flag": false,
    "gras_status": false,
    "ifra_category": "string",
    "allergen_flag": false,
    "colorant_flag": false,
    "origin_details": {"regions": [], "source_material": "string", "processing_methods": []},
    "primary_functions": [],
    "regulatory_notes": [],
    "documentation": {"references": [], "last_verified": "ISO-8601 date"}
  },
  "data_quality": {"confidence": 0-1, "caveats": []}
}
"""

CLUSTER_TERM_SCHEMA_SPEC = r"""
{
  "term": "canonical base term",
  "common_name": "TRUE vernacular name (e.g., Silver Fir not Abies Alba)",
  "maker_priority": 1-10,
  "ingredient_core": {
    "origin": {"value": "Plant-Derived|Animal-Derived|Animal-Byproduct|Mineral/Earth|Synthetic|Fermentation|Marine-Derived", "status": "found|not_found|not_applicable"},
    "ingredient_category": {"value": "Fruits|Vegetables|Grains|Nuts|Seeds|Spices|Herbs|Flowers|Roots|Barks|Clays|Minerals|Salts|Sugars", "status": "found|not_found"},
    "base_refinement": {"value": "Raw/Whole|Minimally Processed|Fermented|Synthesized", "status": "found"},
    "derived_from": {"value": "string", "status": "found|not_applicable"},
    "botanical_name": {"value": "Latin binomial", "status": "found|not_found|not_applicable"},
    "inci_name": {"value": "INCI name", "status": "found|not_found"},
    "cas_number": {"value": "CAS number", "status": "found|not_found"},
    "short_description": "one sentence",
    "detailed_description": "2-3 sentences"
  },
  "data_quality": {"confidence": 0-1, "caveats": []}
}
"""

ITEMS_SCHEMA_SPEC = r"""
{
  "items": [{
    "variation": {"value": "string", "status": "found|not_applicable"},
    "description": "1-2 sentence description",
    "physical_form": {"value": "Oil|Liquid|Powder|Granules|Crystals|Whole|Butter|Wax|Resin|Gel|Paste|Flakes|Chunks", "status": "found"},
    "processing_method": {"value": "Unprocessed|Cold Pressed|Expeller Pressed|Solvent Extracted|Steam Distilled|CO2 Extracted|Refined|Bleached|Deodorized|Hydrogenated|Fractionated|Filtered|Milled|Dried|Freeze-Dried|Fermented|Synthesized", "status": "found"},
    "color": "typical color (or Not Found)",
    "odor_profile": "scent characteristics (or Odorless or Not Found)",
    "flavor_profile": "taste (or Not edible or Not Found)",
    "synonyms": [],
    "applications": ["3-5 uses: Soapmaking, Skincare, Haircare, Aromatherapy, Culinary, etc"],
    "function_tags": ["3-5 functions: Emollient, Moisturizing, Cleansing, Fragrance, etc"],
    "safety_tags": [],
    "shelf_life_days": 30-3650,
    "sds_hazards": [],
    "storage": {"temperature_celsius": {"min": 5, "max": 25}, "humidity_percent": {"max": 60}, "special_instructions": "string"},
    "specifications": {
      "sap_naoh": "number or N/A or Not Found",
      "sap_koh": "number or N/A or Not Found",
      "iodine_value": "number or N/A or Not Found",
      "melting_point_celsius": {"min": "number or N/A", "max": "number or N/A"},
      "flash_point_celsius": "number or N/A or Not Found",
      "ph_range": {"min": "number or N/A", "max": "number or N/A"},
      "usage_rate_percent": {"leave_on_max": "number or N/A", "rinse_off_max": "number or N/A"},
      "density_g_ml": "number or N/A or Not Found",
      "solubility": "description (e.g., 'Soluble in oil, insoluble in water') or N/A or Not Found"
    },
    "sourcing": {"common_origins": [], "certifications": [], "supply_risks": [], "sustainability_notes": "string"},
    "default_unit": "gram|kg|oz|lb|ml|liter|floz|count",
    "form_bypass": false,
    "variation_bypass": false
  }],
  "data_quality": {"confidence": 0-1, "caveats": []}
}
MANDATORY RULES - EVERY FIELD MUST HAVE AN EXPLICIT ANSWER:
- If you have data → provide the value
- If not applicable (e.g., pH for oils, SAP for non-lipids) → "N/A"
- If unknown/obscure → "Not Found"
- NEVER leave a field empty or omit it. Every field in the schema must appear with an answer.
UNITS: Oils/Liquids→ml, Butters/Waxes/Powders→oz or gram, Whole→count.
"""

TAXONOMY_SCHEMA_SPEC = r"""
Return JSON using this schema (lists sorted alphabetically):
{
  "taxonomy": {
    "scent_profile": ["string"],
    "color_profile": ["string"],
    "texture_profile": ["string"],
    "compatible_processes": ["string"],
    "incompatible_processes": ["string"]
  }
}
"""


def _call_openai_json(client: openai.OpenAI, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        temperature=TEMPERATURE,
        max_tokens=4096,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("OpenAI returned empty response content")
    payload = json.loads(content.strip())
    if not isinstance(payload, dict):
        raise ValueError("AI response was not a JSON object")
    return payload


def _filter_source_data(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Filter source metadata to only essential fields, reducing token usage by ~70%."""
    if not meta:
        return {}
    
    # Essential fields to keep from each source
    KEEP_FIELDS = {
        "cas_number", "cas", "cas_no", "CAS",
        "inci_name", "inci", "INCI",
        "botanical_name", "scientific_name", "latin_name",
        "common_name", "name", "ingredient_name",
        "description", "definition",
        "functions", "function", "cosmetic_functions",
        "restrictions", "restriction",
        "molecular_formula", "formula",
        "molecular_weight", "mol_weight",
        "density", "specific_gravity",
        "melting_point", "boiling_point", "flash_point",
        "odor", "odor_description", "flavor", "flavor_description",
        "color", "appearance",
        "solubility",
        "safety", "hazards", "warnings",
        "origin", "source",
    }
    
    filtered = {}
    for source_name, source_data in meta.items():
        if not isinstance(source_data, dict):
            continue
        source_filtered = {}
        for key, value in source_data.items():
            key_lower = key.lower().replace("_", "").replace("-", "")
            if any(keep.lower().replace("_", "") in key_lower for keep in KEEP_FIELDS):
                # Truncate very long values
                if isinstance(value, str) and len(value) > 500:
                    value = value[:500] + "..."
                source_filtered[key] = value
        if source_filtered:
            filtered[source_name] = source_filtered
    return filtered


def _render_metadata_blob(term: str) -> str:
    if sources is None:
        return "{}"
    try:
        meta = sources.fetch_metadata(term)
        if not meta:
            return "{}"
        filtered = _filter_source_data(meta)
        return json.dumps(filtered, ensure_ascii=False, sort_keys=True) if filtered else "{}"
    except Exception:  # pragma: no cover
        return "{}"


def _render_core_prompt(term: str, base_context: Dict[str, Any]) -> str:
    meta = _render_metadata_blob(term)
    origins = ", ".join(ORIGINS)
    primaries = ", ".join(INGREDIENT_CATEGORIES_PRIMARY)
    refinements = ", ".join(REFINEMENT_LEVELS)
    base_blob = json.dumps(base_context, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""
You are Stage 2A (Compilation — Core). Build canonical core fields for the base ingredient term: "{term}".

Rules:
- Prefer the normalized base context when it looks correct.
- If any provided identity field looks clearly wrong, malformed, or missing (botanical_name / inci_name / cas_number), you MAY correct it in your output.
- If you correct or override a provided field, mention that in data_quality.caveats (briefly).
- origin is REQUIRED and must be one of: {origins}
- ingredient_category is REQUIRED and must be one of: {primaries}
- refinement_level is REQUIRED and must be one of: {refinements}
- Do NOT invent marketing language. Be concise and factual.
- Use the provided external metadata as hints when available.
- ingredient_core.category MUST be one of: {", ".join(INGREDIENT_CATEGORIES)}

External metadata (may be empty):
{meta}

Normalized base context (do not contradict):
{base_blob}

SCHEMA:
{CORE_SCHEMA_SPEC}
"""


def _render_cluster_term_prompt(cluster_id: str, cluster_context: Dict[str, Any]) -> str:
    """Stage 1 prompt: pick canonical base term from a raw cluster."""
    meta = json.dumps(cluster_context, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""
You are Stage 1 (Term Completion / Normalization).

TASK:
- Given one RAW ingestion cluster, determine the single canonical BASE ingredient term for the entire cluster.
- Complete the core identity fields for that term using the cluster evidence.
- Assign a maker_priority score (1-10) based on how commonly this ingredient is used by artisan makers.

MAKER PRIORITY SCORING (1-10):
10 = Essential staples (coconut oil, olive oil, shea butter, lye, beeswax, soy wax)
9 = Very common oils/butters (castor oil, sweet almond, cocoa butter, palm oil)
8 = Popular essential oils (lavender, tea tree, peppermint, eucalyptus, lemon)
7 = Common specialty oils/butters (jojoba, argan, mango butter, avocado oil)
6 = Popular additives (vitamin E, honey, oatmeal, clays, activated charcoal)
5 = Specialty essential oils (ylang ylang, frankincense, patchouli, geranium)
4 = Less common botanicals/extracts (neem, tamanu, sea buckthorn)
3 = Specialty/rare ingredients (exotic butters, uncommon carrier oils)
2 = Industrial/niche cosmetic chemicals
1 = Rare/obscure ingredients with limited maker use

CRITICAL RULES:
- Every cluster must map to ONE base term.
- The base term must NOT include variation/form/processing words.
  Examples:
  - "Hydrolyzed Shea Butter" -> "Shea" (or "Shea Butter" ONLY if "butter" is truly the ingredient identity, not the form)
  - "Coconut Butter" -> "Coconut"
  - "Lavender Essential Oil" -> "Lavender"
  - "Apricot Kernel Oil" -> "Apricot"
- Treat words like hydrolyzed, deodorized, refined, unrefined, filtered, hydrogenated, oil, butter, wax, resin, powder, extract, tincture, glycerite, hydrosol, solution, concentrate as NOT part of the base term unless the cluster evidence strongly indicates otherwise.
- Prefer what the CLUSTER implies: multiple items in the cluster should share the same base term.
- Use INCI/CAS/botanical evidence from the cluster when available. Do not invent identifiers.

NO SILENT BYPASS - EVERY FIELD MUST BE EXPLICITLY HANDLED:
Every field in ingredient_core must return: {{"value": <data>, "status": "found|not_found|not_applicable", "reason": <string if not found/not applicable>}}

TERM-LEVEL vs ITEM-LEVEL DISTINCTION (CRITICAL):
- base_refinement at TERM level describes the natural state of the base ingredient:
  * Apricot (the fruit) = "Raw/Whole"
  * Butter (dairy product) = "Minimally Processed" (churned from cream)
  * Vinegar = "Fermented"
  * Sodium Hydroxide = "Synthesized"
- Processing like oil extraction, distillation, cold-pressing belongs at ITEM level (Stage 2), NOT here!

REQUIRED FIELD HANDLING:
- botanical_name: ALWAYS provide Latin binomial for Plant-Derived (e.g., "Prunus armeniaca"). Use status="not_applicable" for synthetics/minerals.
- inci_name: ALWAYS provide. Use status="not_found" with reason only if genuinely unknown.
- cas_number: Provide if known. Use status="not_found" with reason if unable to determine.

Cluster ID: "{cluster_id}"

Cluster evidence (JSON; use as source-of-truth hints):
{meta}

SCHEMA:
{CLUSTER_TERM_SCHEMA_SPEC}
"""


def normalize_cluster_term(cluster_id: str, cluster_context: Dict[str, Any]) -> Dict[str, Any]:
    """Stage 1: normalize a raw cluster into canonical term + core fields."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")
    cid = (cluster_id or "").strip()
    if not cid:
        raise ValueError("cluster_id is required")
    client = openai.OpenAI(api_key=openai.api_key)
    return _call_openai_json(client, SYSTEM_PROMPT, _render_cluster_term_prompt(cid, cluster_context or {}))


def compile_core(term: str, base_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Stage 2A: compile only the core ingredient fields."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")
    t = (term or "").strip()
    if not t:
        raise ValueError("term is required")
    base_context = base_context or {}
    client = openai.OpenAI(api_key=openai.api_key)
    return _call_openai_json(client, SYSTEM_PROMPT, _render_core_prompt(t, base_context))


def compile_items(
    term: str,
    *,
    ingredient_core: Dict[str, Any],
    base_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Stage 2B: compile items; uses completion mode if base_context.seed_items is present."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")
    t = (term or "").strip()
    if not t:
        raise ValueError("term is required")
    base_context = base_context or {}
    client = openai.OpenAI(api_key=openai.api_key)
    seed_items = base_context.get("seed_items") if isinstance(base_context.get("seed_items"), list) else None
    if seed_items:
        payload = _call_openai_json(client, SYSTEM_PROMPT, _render_items_completion_prompt(t, ingredient_core, base_context))
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        merged_items = _merge_seed_items(
            seed_items=[it for it in seed_items if isinstance(it, dict)],
            ai_items=[it for it in items if isinstance(it, dict)],
        )
        payload["items"] = [_ensure_item_fields(it) for it in merged_items]
        return payload
    payload = _call_openai_json(client, SYSTEM_PROMPT, _render_items_prompt(t, ingredient_core, base_context))
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    payload["items"] = [_ensure_item_fields(it) for it in items if isinstance(it, dict)]
    return payload


def compile_taxonomy(term: str, *, ingredient_core: Dict[str, Any], items: list[dict]) -> Dict[str, Any]:
    """Stage 2C: compile taxonomy tags."""
    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")
    t = (term or "").strip()
    if not t:
        raise ValueError("term is required")
    client = openai.OpenAI(api_key=openai.api_key)
    return _call_openai_json(client, SYSTEM_PROMPT, _render_taxonomy_prompt(t, ingredient_core, items))


def complete_item_stubs(
    term: str,
    *,
    ingredient_core: Dict[str, Any],
    base_context: Dict[str, Any] | None,
    item_stubs: list[dict],
    batch_size: int = 5,
) -> list[dict]:
    """Complete schema fields for an authoritative list of item stubs (identity fields are stable).
    
    For large clusters (>batch_size items), processes in batches to avoid token limits.
    """
    stubs = [it for it in item_stubs if isinstance(it, dict)]
    
    # For small clusters, process all at once
    if len(stubs) <= batch_size:
        ctx = dict(base_context or {})
        ctx["seed_items"] = stubs
        payload = compile_items(term, ingredient_core=ingredient_core, base_context=ctx)
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        return [_ensure_item_fields(it) for it in items if isinstance(it, dict)]
    
    # For large clusters, batch to avoid token limit
    all_items = []
    for i in range(0, len(stubs), batch_size):
        batch = stubs[i:i + batch_size]
        ctx = dict(base_context or {})
        ctx["seed_items"] = batch
        payload = compile_items(term, ingredient_core=ingredient_core, base_context=ctx)
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        all_items.extend([_ensure_item_fields(it) for it in items if isinstance(it, dict)])
    return all_items


def _render_items_prompt(term: str, ingredient_core: Dict[str, Any], base_context: Dict[str, Any]) -> str:
    meta = _render_metadata_blob(term)
    core_blob = json.dumps(ingredient_core, ensure_ascii=False, indent=2, sort_keys=True)
    base_blob = json.dumps(base_context, ensure_ascii=False, indent=2, sort_keys=True)
    forms = ", ".join(PHYSICAL_FORMS)
    variations = ", ".join(VARIATIONS_CURATED)
    return f"""Stage 2B: Create item variants for "{term}".
EVERY FIELD: VALUE, "N/A", or "Not Found". No empty/omitted.
Rules: physical_form∈{{{forms}}}. variation∈{{{variations}}}. applications/function_tags: 3-5. Empty variation→variation_bypass=true. Min 1 item.
SPECS (use training knowledge): SAP(oils 180-260, EO 5-20), Iodine, Density(oils 0.85-0.95), Solubility, pH("N/A" for oils). "Not Found" only if truly obscure.
Core:{core_blob}
Context:{base_blob}
Meta:{meta}
SCHEMA:{ITEMS_SCHEMA_SPEC}"""


def _render_items_completion_prompt(term: str, ingredient_core: Dict[str, Any], base_context: Dict[str, Any]) -> str:
    """Stage 2B variant: complete existing ingestion-derived items (do not invent new ones)."""
    meta = _render_metadata_blob(term)
    core_blob = json.dumps(ingredient_core, ensure_ascii=False, indent=2, sort_keys=True)
    base_blob = json.dumps(base_context, ensure_ascii=False, indent=2, sort_keys=True)
    forms = ", ".join(PHYSICAL_FORMS)
    variations = ", ".join(VARIATIONS_CURATED)
    return f"""Stage 2B COMPLETION: Fill missing fields for "{term}" items.
EVERY FIELD: VALUE, "N/A", or "Not Found". No empty/omitted.
IDENTITY (DO NOT CHANGE): variation, physical_form, form_bypass, variation_bypass. No add/remove/reorder items.
Rules: physical_form∈{{{forms}}}. variation∈{{{variations}}}. applications/function_tags: 3-5.
SPECS (use training knowledge): SAP(oils 180-260, EO 5-20), Iodine, Density(oils 0.85-0.95), Solubility, pH("N/A" for oils). "Not Found" only if truly obscure.
Core:{core_blob}
Context+Seeds:{base_blob}
Meta:{meta}
SCHEMA:{ITEMS_SCHEMA_SPEC}"""


def _merge_fill_only(base: Any, patch: Any) -> Any:
    """Fill-only merge used to prevent overwriting ingestion-derived fields."""

    def _normalize_missing(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        lowered = cleaned.lower()
        if lowered in {"n/a", "na", "not applicable", "not_applicable"}:
            return "N/A"
        if lowered in {"unknown", "not found", "not_found", "none", "null", "nil", "tbd"}:
            return "Not Found"
        return cleaned

    def _is_placeholder(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        lowered = value.strip().lower()
        return lowered in {
            "unknown",
            "not found",
            "not_found",
            "n/a",
            "na",
            "not applicable",
            "not_applicable",
            "none",
            "null",
            "nil",
            "tbd",
        }

    if isinstance(patch, str):
        patch = _normalize_missing(patch)
    if isinstance(base, dict) and isinstance(patch, dict):
        out = dict(base)
        for k, v in patch.items():
            existing = out.get(k)
            if existing not in (None, "", [], {}) and not _is_placeholder(existing):
                continue
            if v in (None, "", [], {}):
                continue
            out[k] = _normalize_missing(v)
        return out
    if isinstance(base, list) and isinstance(patch, list):
        if not base or all(_is_placeholder(v) for v in base if isinstance(v, str)):
            return patch
        return base
    if isinstance(base, str) and _is_placeholder(base):
        base = ""
    return base if base not in (None, "") else patch


def _merge_seed_items(seed_items: list[dict], ai_items: list[dict]) -> list[dict]:
    """Merge AI-completed fields onto ingestion seed items while enforcing identity stability."""
    if not seed_items:
        return ai_items
    out: list[dict] = []
    for idx, seed in enumerate(seed_items):
        ai = ai_items[idx] if idx < len(ai_items) and isinstance(ai_items[idx], dict) else {}
        merged = dict(seed)

        # Identity fields are authoritative from seed.
        for k in ("variation", "physical_form", "form_bypass", "variation_bypass"):
            merged[k] = seed.get(k)

        # Fill-only merge for the rest.
        for k, v in ai.items():
            if k in ("variation", "physical_form", "form_bypass", "variation_bypass"):
                continue
            if k == "specifications":
                merged["specifications"] = _merge_fill_only(seed.get("specifications", {}), v)
                continue
            merged[k] = _merge_fill_only(seed.get(k), v)

        out.append(merged)
    return out


REQUIRED_SPEC_FIELDS_SCALAR = {"sap_naoh", "sap_koh", "iodine_value", "flash_point_celsius", "density_g_ml", "solubility"}
REQUIRED_SPEC_FIELDS_RANGE = {"melting_point_celsius", "ph_range"}
REQUIRED_SPEC_FIELDS_USAGE = {"usage_rate_percent"}

REQUIRED_ITEM_FIELDS = {
    "variation", "description", "physical_form", "processing_method", "color",
    "odor_profile", "flavor_profile", "synonyms", "applications", "function_tags",
    "safety_tags", "shelf_life_days", "sds_hazards", "storage", "specifications",
    "sourcing", "default_unit", "form_bypass", "variation_bypass"
}


def _ensure_item_fields(item: dict) -> dict:
    """Ensure all required fields are present with at least a placeholder value."""
    for field in REQUIRED_ITEM_FIELDS:
        if field not in item:
            if field in ("synonyms", "sds_hazards"):
                item[field] = []
            elif field in ("applications", "function_tags", "safety_tags"):
                item[field] = ["Not Found"]
            elif field in ("specifications",):
                item[field] = {}
            elif field == "storage":
                item[field] = {"temperature_celsius": {"min": "N/A", "max": "N/A"}, "humidity_percent": {"max": "N/A"}, "special_instructions": "Not Found"}
            elif field == "sourcing":
                item[field] = {"common_origins": [], "certifications": [], "supply_risks": [], "sustainability_notes": "Not Found"}
            elif field in ("form_bypass", "variation_bypass"):
                item[field] = False
            else:
                item[field] = "Not Found"
    
    # Ensure applications/functions have at least one entry
    for list_field in ("applications", "function_tags", "safety_tags"):
        val = item.get(list_field)
        if not val or (isinstance(val, list) and len(val) == 0):
            item[list_field] = ["Not Found"]
    
    # Ensure spec fields with proper types
    specs = item.get("specifications", {})
    if not isinstance(specs, dict):
        specs = {}
    
    # Scalar fields
    for spec_field in REQUIRED_SPEC_FIELDS_SCALAR:
        if spec_field not in specs:
            specs[spec_field] = "Not Found"
    
    # Range fields (min/max structure)
    for spec_field in REQUIRED_SPEC_FIELDS_RANGE:
        if spec_field not in specs or not isinstance(specs.get(spec_field), dict):
            specs[spec_field] = {"min": "N/A", "max": "N/A"}
        else:
            rng = specs[spec_field]
            if "min" not in rng:
                rng["min"] = "N/A"
            if "max" not in rng:
                rng["max"] = "N/A"
    
    # Usage rate (leave_on_max/rinse_off_max structure)
    for spec_field in REQUIRED_SPEC_FIELDS_USAGE:
        if spec_field not in specs or not isinstance(specs.get(spec_field), dict):
            specs[spec_field] = {"leave_on_max": "N/A", "rinse_off_max": "N/A"}
        else:
            usage = specs[spec_field]
            if "leave_on_max" not in usage:
                usage["leave_on_max"] = "N/A"
            if "rinse_off_max" not in usage:
                usage["rinse_off_max"] = "N/A"
    
    item["specifications"] = specs
    return item


def _render_taxonomy_prompt(term: str, ingredient_core: Dict[str, Any], items: list[dict]) -> str:
    core_blob = json.dumps(ingredient_core, ensure_ascii=False, indent=2, sort_keys=True)
    items_blob = json.dumps(items[:6], ensure_ascii=False, indent=2, sort_keys=True)
    return f"""
You are Stage 2C (Compilation — Taxonomy). Generate taxonomy tags for base ingredient: "{term}".

Context (core):
{core_blob}

Context (sample items):
{items_blob}

SCHEMA:
{TAXONOMY_SCHEMA_SPEC}
"""


def _render_prompt(ingredient_name: str) -> str:
    return PROMPT_TEMPLATE.format(
        common_name=ingredient_name.strip(),
        ingredient=ingredient_name.strip(),
        schema=JSON_SCHEMA_SPEC,
        error_object=json.dumps(ERROR_OBJECT),
        categories=", ".join(INGREDIENT_CATEGORIES),
    )


def get_ingredient_data(ingredient_name: str, base_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Fetch structured data for a single ingredient via the OpenAI API."""

    if not ingredient_name or not ingredient_name.strip():
        raise ValueError("ingredient_name is required")

    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")

    term = ingredient_name.strip()
    base_context = base_context or {}
    user_prompt = _render_prompt(term)
    last_error: Exception | None = None

    client = openai.OpenAI(api_key=openai.api_key)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if not MULTI_PROMPT_MODE:
                return _call_openai_json(client, SYSTEM_PROMPT, user_prompt)

            # Stage 2A: core
            core_payload = _call_openai_json(client, SYSTEM_PROMPT, _render_core_prompt(term, base_context))
            ingredient_core = core_payload.get("ingredient_core") if isinstance(core_payload.get("ingredient_core"), dict) else {}

            # Stage 2B: items
            seed_items = base_context.get("seed_items") if isinstance(base_context.get("seed_items"), list) else None
            if seed_items:
                items_payload = _call_openai_json(client, SYSTEM_PROMPT, _render_items_completion_prompt(term, ingredient_core, base_context))
            else:
                items_payload = _call_openai_json(client, SYSTEM_PROMPT, _render_items_prompt(term, ingredient_core, base_context))
            items = items_payload.get("items") if isinstance(items_payload.get("items"), list) else []
            if seed_items:
                items = _merge_seed_items(seed_items=[it for it in seed_items if isinstance(it, dict)], ai_items=[it for it in items if isinstance(it, dict)])
            # Apply field validation to all items
            items = [_ensure_item_fields(it) for it in items if isinstance(it, dict)]

            # Stage 2C: taxonomy
            taxonomy_payload = _call_openai_json(client, SYSTEM_PROMPT, _render_taxonomy_prompt(term, ingredient_core, items))
            taxonomy = taxonomy_payload.get("taxonomy") if isinstance(taxonomy_payload.get("taxonomy"), dict) else {}

            # Assemble final payload matching the full schema.
            # Merge rule: base_context wins for identity fields (term, inci, cas, botanical).
            ingredient: Dict[str, Any] = dict(ingredient_core)
            ingredient["common_name"] = term
            for k in ("botanical_name", "inci_name", "cas_number"):
                v = (base_context.get(k) or "").strip() if isinstance(base_context.get(k), str) else base_context.get(k)
                if v:
                    ingredient[k] = v
            ingredient["items"] = items
            ingredient["taxonomy"] = taxonomy

            # Documentation may be missing; keep shape stable.
            if "documentation" not in ingredient:
                ingredient["documentation"] = {"references": [], "last_verified": None}

            confidence = core_payload.get("data_quality", {}).get("confidence") if isinstance(core_payload.get("data_quality"), dict) else None
            if not isinstance(confidence, (int, float)):
                confidence = 0.7
            caveats: list[str] = []
            for blob in (core_payload, items_payload):
                dq = blob.get("data_quality") if isinstance(blob.get("data_quality"), dict) else {}
                for c in dq.get("caveats", []) if isinstance(dq.get("caveats"), list) else []:
                    if isinstance(c, str) and c.strip():
                        caveats.append(c.strip())

            return {
                "ingredient": ingredient,
                "data_quality": {"confidence": float(confidence), "caveats": sorted(set(caveats))},
            }
        except json.JSONDecodeError as exc:
            last_error = exc
            LOGGER.warning("JSON decoding failed for %s (attempt %s): %s", term, attempt, exc)
        except Exception as exc:  # pylint: disable=broad-except
            last_error = exc
            LOGGER.warning("OpenAI call failed for %s (attempt %s): %s", term, attempt, exc)

        time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    error_message = (
        f"Failed to compile ingredient '{ingredient_name}' after {MAX_RETRIES} attempts: {last_error}"
    )
    LOGGER.error(error_message)
    return {"error": error_message}