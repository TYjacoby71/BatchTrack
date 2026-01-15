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

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
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
    "You are IngredientCompilerGPT, an expert data extraction agent for artisanal "
    "manufacturing. You only output JSON that conforms to the provided schema. "
    "CRITICAL: Do not fabricate facts or numeric properties; omit unknown optional fields "
    "(or use null) instead of placeholder strings like 'unknown'/'n/a'."
)

JSON_SCHEMA_SPEC = r"""
Return JSON using this schema (all strings trimmed, booleans only true/false, lists sorted alphabetically):
{
  "ingredient": {
    "common_name": "string (required)",
    "category": "one of the approved ingredient categories",
    "botanical_name": "string",
    "inci_name": "string",
    "cas_number": "string",
    "short_description": "string",
    "detailed_description": "string",
    "origin": {
      "regions": ["string"],
      "source_material": "string",
      "processing_methods": ["Cold Pressed", "Solvent Extracted", ...]
    },
    "primary_functions": ["Emollient", "Humectant", "Bulking", ...],
    "regulatory_notes": ["IFRA safe", "Food grade", ...],
    "items": [
      {
        "item_name": "Shea Butter (Refined)",
        "variation": "string (e.g., Refined, Unrefined, Cold Pressed, 2%, Filtered, Essential Oil, CO2 Extract, Tincture, 50% Solution; empty string if none)",
        "physical_form": "short noun for physical state (e.g., Oil, Liquid, Powder, Granules, Crystals, Whole, Butter, Wax, Resin, Gel, Paste, Syrup, Concentrate)",
        "synonyms": ["aka", ...],
        "applications": ["Soap", "Bath Bomb", "Chocolate", "Lotion", "Candle"],
        "function_tags": ["Stabilizer", "Fragrance", "Colorant", "Binder", "Fuel"],
        "safety_tags": ["Dermal Limit 3%", "Photosensitizer", ...],
          "shelf_life_days": 30-3650,
        "sds_hazards": ["Flammable", "Allergen"],
        "storage": {
          "temperature_celsius": {"min": 5, "max": 25},
          "humidity_percent": {"max": 60},
          "special_instructions": "Keep out of light"
        },
        "specifications": {
          "sap_naoh": 0.128,
          "sap_koh": 0.18,
          "iodine_value": 10,
          "melting_point_celsius": {"min": 30, "max": 35},
          "flash_point_celsius": 200,
          "ph_range": {"min": 5, "max": 7}
        },
        "sourcing": {
          "common_origins": ["Ghana", "Ivory Coast"],
          "certifications": ["Organic", "Fair Trade"],
          "supply_risks": ["Seasonal Harvest"],
          "sustainability_notes": "Tree nut resource"
        },
        "form_bypass": true | false,  // when true, display should use item_name alone (e.g., Water, Ice)
        "variation_bypass": true | false  // when true, UI can omit displaying variation (useful when variation is implicit)
      }
    ],
    "taxonomy": {
      "scent_profile": ["Fruity", "Nutty"],
      "color_profile": ["Ivory", "Translucent"],
      "texture_profile": ["Brittle", "Soft"],
      "compatible_processes": ["Cold Process Soap", "Hot Process", "Sugar Confectionery", "Emulsion", "Anhydrous Balm", "Pressed Powder", "Small Batch Brewing"],
      "incompatible_processes": ["High-heat frying"]
    },
    "documentation": {
      "references": [
        {
          "title": "USP Monograph",
          "url": "https://example.com",
          "notes": "Key regulatory reference"
        }
      ],
      "last_verified": "ISO-8601 date"
    }
  },
  "data_quality": {
    "confidence": 0-1 float,
    "caveats": ["string"]
  }
}
"""

ERROR_OBJECT = {"error": "Unable to return ingredient payload"}

PROMPT_TEMPLATE = """
You are an expert ingredient data compiler.

TASK: Build the complete ingredient dossier for: "{ingredient}".

CONTEXT:
- Audience: artisanal formulators in soap, confections, cosmetics, herbalism, fermentation, aromatherapy, and small-batch baking.
- Scope: RAW INGREDIENTS ONLY. Never include packaging, containers, utensils, or finished consumer goods.
- Item model: An ITEM is the combination of BASE INGREDIENT + VARIATION.
  - VARIATION is the purchasable/spec distinction (e.g., Refined vs Unrefined, 2% vs Whole, Filtered vs Unfiltered, Organic, Deodorized, 50% Solution).
  - PHYSICAL FORM is still required and must remain a short noun (e.g., Powder, Oil, Liquid, Granules). Do not encode variations into physical_form.
  - Do NOT generate a final display name; the system will derive item_name in code from (base + variation + physical_form + bypass flags).
  - If the base is normally sold in multiple forms (powder vs liquid vs whole), create separate items per form and specify variation/form fields appropriately.
- Create a dedicated `items` entry for each common purchasable variation and/or physical form used in craft production.
- Populate every applicable attribute in the schema. Use "unknown" only when absolutely no data exists.
- Use authoritative references (USP, FCC, cosmetic suppliers, herbal materia medica) when citing specs.
- Use metric units. Shelf life must be expressed in DAYS (convert from months/years when needed). Temperature in Celsius.
- All string values must be clear, sentence case, and free of marketing fluff.
- Return strictly valid JSON (UTF-8, double quotes, no trailing commas). If you are uncertain, respond with {{"error": "explanation"}}.

CONTROLLED VOCAB REMINDERS:
- physical_form must be a short noun (e.g., "Powder", "Chips", "Pellets", "Whole", "Puree", "Pressed Cake").
- function_tags should draw from: Emollient, Humectant, Surfactant, Emulsifier, Preservative, Antioxidant, Colorant, Fragrance, Exfoliant, Thickener, Binder, Fuel, Hardener, Stabilizer, Plasticizer, Chelator, Buffer, Flavor, Sweetener, Bittering Agent, Fermentation Nutrient.
- applications should be chosen from: Cold Process Soap, Hot Process Soap, Melt & Pour Soap, Lotion, Cream, Balm, Serum, Scrub, Perfume, Candle, Wax Melt, Lip Balm, Chocolate, Confection, Baked Good, Beverage, Fermented Beverage, Herbal Tincture, Hydro-distillation, Bath Bomb, Shower Steamer, Haircare, Skincare, Deodorant, Cleaner, Detergent, Paint, Dye Bath.
- ingredient.category must be one of: {categories}

FORM & SOLUTION GUIDANCE:
- Always include common dairy *variations* (e.g., whole milk, 2% milk, skim milk, skim milk powder) as distinct items.
- Include buffered/stock solutions (e.g., 50% Sodium Hydroxide Solution, 20% Potassium Carbonate Solution) as distinct items; encode the %/strength in item_name.
- Essential oils, hydrosols, absolutes, CO2 extracts, glycerites, tinctures, macerations, and infusions should be represented as distinct forms under the parent ingredient.
- When an ingredient should display without a suffix (Water, Ice, Steam), set `form_bypass`=true so the interface shows just "Water" or "Ice" while still recording the underlying physical_form.
- More generally, if the best default item is identical to the base common_name (e.g., "Water", "Apples"), set `item_name` exactly to the common_name and set `form_bypass`=true so the UI shows the base without a redundant suffix.
- When no better industry name exists, use a concise solution label such as "Potassium Carbonate Solution (20%)" or simply "Brine Solution".

VARIATION vs PHYSICAL_FORM (IMPORTANT):
- Put "Essential Oil", "CO2 Extract", "Absolute", "Hydrosol", "Tincture", "Glycerite", "% Solution", "Cold Pressed", "Refined", "Filtered", etc. in `variation`.
- Keep `physical_form` as the physical state noun only (Oil, Liquid, Powder, Whole, Granules, Crystals, Butter, Wax, Resin, Gel, Paste, Syrup, Concentrate).
- `item_name` should generally be: "{common_name} (variation)" when variation is non-empty.
- Do NOT emit `item_name` as a source-of-truth; code will derive it. If `variation` is empty, set `variation_bypass`=true.

SCHEMA (required):
{schema}

OUTPUT CONTRACT:
- Respond with a single JSON object adhering to the schema.
- If ingredient is out of scope or data unavailable, return {error_object} with a precise message.
"""

CORE_SCHEMA_SPEC = r"""
Return JSON using this schema (all strings trimmed):
{
  "ingredient_core": {
    "origin": "one of: Plant-Derived, Animal-Derived, Animal-Byproduct, Mineral/Earth, Synthetic, Fermentation, Marine-Derived",
    "ingredient_category": "one of the curated Ingredient Categories (base-level primary): Fruits & Berries, Vegetables, Grains, Nuts, Seeds, Spices, Herbs, Flowers, Roots, Barks, Clays, Minerals, Salts, Sugars, Liquid Sweeteners, Acids",
    "refinement_level": "one of: Raw/Unprocessed, Minimally Processed, Extracted/Distilled, Milled/Ground, Fermented, Synthesized, Extracted Fat, Other",
    "derived_from": "string (optional; natural source if base is derived)",
    "category": "one of the approved ingredient categories",
    "botanical_name": "string",
    "inci_name": "string",
    "cas_number": "string",
    "short_description": "string",
    "detailed_description": "string",
    "usage_restrictions": "string",
    "prohibited_flag": true | false,
    "gras_status": true | false,
    "ifra_category": "string",
    "allergen_flag": true | false,
    "colorant_flag": true | false,
    "origin_details": {
      "regions": ["string"],
      "source_material": "string",
      "processing_methods": ["Cold Pressed", "Solvent Extracted", ...]
    },
    "primary_functions": ["Emollient", "Humectant", ...],
    "regulatory_notes": ["string"],
    "documentation": {
      "references": [{"title": "string", "url": "string", "notes": "string"}],
      "last_verified": "ISO-8601 date"
    }
  },
  "data_quality": {"confidence": 0-1 float, "caveats": ["string"]}
}
"""

CLUSTER_TERM_SCHEMA_SPEC = r"""
Return JSON using this schema (all strings trimmed):
{
  "term": "string (required) - canonical base ingredient term (no form/variation words)",
  "ingredient_core": {
    "origin": "one of: Plant-Derived, Animal-Derived, Animal-Byproduct, Mineral/Earth, Synthetic, Fermentation, Marine-Derived",
    "ingredient_category": "one of the curated Ingredient Categories (base-level primary): Fruits & Berries, Vegetables, Grains, Nuts, Seeds, Spices, Herbs, Flowers, Roots, Barks, Clays, Minerals, Salts, Sugars, Liquid Sweeteners, Acids",
    "refinement_level": "one of: Raw/Unprocessed, Minimally Processed, Extracted/Distilled, Milled/Ground, Fermented, Synthesized, Extracted Fat, Other",
    "derived_from": "string (optional; natural source if base is derived)",
    "category": "one of the approved ingredient categories",
    "botanical_name": "string",
    "inci_name": "string",
    "cas_number": "string",
    "short_description": "string",
    "detailed_description": "string"
  },
  "data_quality": {"confidence": 0-1 float, "caveats": ["string"]}
}
"""

ITEMS_SCHEMA_SPEC = r"""
Return JSON using this schema (all strings trimmed; lists sorted alphabetically):
{
  "items": [
    {
      "variation": "string",
      "physical_form": "one of the curated Physical Forms enum",
      "synonyms": ["aka", ...],
      "applications": ["Soap", "Bath Bomb", "Chocolate", "Lotion", "Candle"],
      "function_tags": ["Stabilizer", "Fragrance", "Colorant", "Binder", "Fuel"],
      "safety_tags": ["string"],
      "shelf_life_days": 30-3650,
      "sds_hazards": ["string"],
      "storage": {
        "temperature_celsius": {"min": 5, "max": 25},
        "humidity_percent": {"max": 60},
        "special_instructions": "string"
      },
      "specifications": {
        "sap_naoh": 0.128,
        "sap_koh": 0.18,
        "iodine_value": 10,
        "melting_point_celsius": {"min": 30, "max": 35},
        "flash_point_celsius": 200,
        "ph_range": {"min": 5, "max": 7},
        "usage_rate_percent": {"leave_on_max": 5, "rinse_off_max": 15}
        // Optional physchem (when known; OK to omit):
        // "density_g_ml": 0.91,  // numeric only; g/mL; include ONLY when known (do not guess)
        // "viscosity_cps": 1200,
        // "refractive_index": 1.44,
        // "molecular_formula": "C3H8O3",
        // "molecular_weight": 92.09,
        // "boiling_point_celsius": 290,
        // "solubility": {"in_water": "string", "in_oil": "string"},
        // "miscible_with": ["string"],
        // "emulsification": {"hlb": 15.0, "oil_in_water": true, "water_in_oil": false}
      },
      "sourcing": {
        "common_origins": ["string"],
        "certifications": ["string"],
        "supply_risks": ["string"],
        "sustainability_notes": "string"
      },
      "form_bypass": true | false,
      "variation_bypass": true | false
    }
  ],
  "data_quality": {"confidence": 0-1 float, "caveats": ["string"]}
}
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


def _render_metadata_blob(term: str) -> str:
    if sources is None:
        return "{}"
    try:
        meta = sources.fetch_metadata(term)
        return json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=True) if meta else "{}"
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

CRITICAL RULES:
- Every cluster must map to ONE base term.
- The base term must NOT include variation/form/processing words.
  Examples:
  - "Hydrolyzed Shea Butter" -> "Shea" (or "Shea Butter" ONLY if "butter" is truly the ingredient identity, not the form)
  - "Coconut Butter" -> "Coconut"
  - "Lavender Essential Oil" -> "Lavender"
- Treat words like hydrolyzed, deodorized, refined, unrefined, filtered, hydrogenated, oil, butter, wax, resin, powder, extract, tincture, glycerite, hydrosol, solution, concentrate as NOT part of the base term unless the cluster evidence strongly indicates otherwise.
- Prefer what the CLUSTER implies: multiple items in the cluster should share the same base term.
- Use INCI/CAS/botanical evidence from the cluster when available. Do not invent identifiers.

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
        payload["items"] = _merge_seed_items(
            seed_items=[it for it in seed_items if isinstance(it, dict)],
            ai_items=[it for it in items if isinstance(it, dict)],
        )
        return payload
    return _call_openai_json(client, SYSTEM_PROMPT, _render_items_prompt(t, ingredient_core, base_context))


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
) -> list[dict]:
    """Complete schema fields for an authoritative list of item stubs (identity fields are stable)."""
    ctx = dict(base_context or {})
    ctx["seed_items"] = [it for it in item_stubs if isinstance(it, dict)]
    payload = compile_items(term, ingredient_core=ingredient_core, base_context=ctx)
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return [it for it in items if isinstance(it, dict)]


def _render_items_prompt(term: str, ingredient_core: Dict[str, Any], base_context: Dict[str, Any]) -> str:
    meta = _render_metadata_blob(term)
    core_blob = json.dumps(ingredient_core, ensure_ascii=False, indent=2, sort_keys=True)
    base_blob = json.dumps(base_context, ensure_ascii=False, indent=2, sort_keys=True)
    forms = ", ".join(PHYSICAL_FORMS)
    variations = ", ".join(VARIATIONS_CURATED)
    return f"""
You are Stage 2B (Compilation — Items). Create purchasable ITEM variants for base ingredient: "{term}".

Rules:
- ITEM = base + variation + physical_form. Variation must capture: Essential Oil / CO2 Extract / Absolute / Hydrosol / Extract / Tincture / Glycerite / % Solution / Refined / Unrefined / Cold Pressed / Filtered, etc.
- physical_form must be one of: {forms}
- variation should usually be chosen from this curated list when applicable: {variations}
- applications must include at least 1 value.
- If variation is empty, set variation_bypass=true.
- Return multiple items when common (at least 1).
- Missing data policy: NEVER use placeholder strings like "unknown" or "n/a". For unknown optional fields, omit the field or set it to null.
- Numeric/spec policy: NEVER guess numeric values (e.g., density, flash point, melting point, pH). Only include numeric specs when you are confident they are real; otherwise omit them.
- Density policy: If you provide density, use specifications.density_g_ml as a NUMBER in g/mL (no unit strings), and only when it makes sense for the physical_form (liquids/oils/syrups).

Ingredient core (context):
{core_blob}

Normalized base context (context):
{base_blob}

External metadata (may be empty):
{meta}

SCHEMA:
{ITEMS_SCHEMA_SPEC}
"""


def _render_items_completion_prompt(term: str, ingredient_core: Dict[str, Any], base_context: Dict[str, Any]) -> str:
    """Stage 2B variant: complete existing ingestion-derived items (do not invent new ones)."""
    meta = _render_metadata_blob(term)
    core_blob = json.dumps(ingredient_core, ensure_ascii=False, indent=2, sort_keys=True)
    base_blob = json.dumps(base_context, ensure_ascii=False, indent=2, sort_keys=True)
    forms = ", ".join(PHYSICAL_FORMS)
    variations = ", ".join(VARIATIONS_CURATED)
    return f"""
You are Stage 2B (Compilation — Items COMPLETION). You are given the authoritative list of items derived deterministically from ingestion for base ingredient: "{term}".

Rules (CRITICAL):
- DO NOT add items.
- DO NOT remove items.
- DO NOT reorder items.
- DO NOT change identity fields for any item: variation, physical_form, form_bypass, variation_bypass.
- Your job is ONLY to fill missing schema fields (applications, function_tags, safety_tags, storage, specifications, sourcing, etc.).
- physical_form must be one of: {forms}
- variation should usually be chosen from this curated list when applicable: {variations}
- applications must include at least 1 value (use ["Unknown"] only if you truly cannot infer anything).
- Missing data policy: NEVER use placeholder strings like "unknown" or "n/a". For unknown optional fields, omit the field or set it to null.
- Numeric/spec policy: NEVER guess numeric values (density, SAP, iodine, pH, flash point, melting point). Only include numeric specs when you are confident they are real; otherwise omit them.
- Density policy: If you provide density, use specifications.density_g_ml as a NUMBER in g/mL (no unit strings), and only when it makes sense for the physical_form (liquids/oils/syrups).

Ingredient core (context):
{core_blob}

Normalized base context (includes seed items to complete; do not contradict):
{base_blob}

External metadata (may be empty):
{meta}

SCHEMA:
{ITEMS_SCHEMA_SPEC}
"""


def _merge_fill_only(base: Any, patch: Any) -> Any:
    """Fill-only merge used to prevent overwriting ingestion-derived fields."""
    if isinstance(patch, str) and patch.strip().lower() in {"unknown", "n/a", "na", "none", "null"}:
        patch = ""
    if isinstance(base, dict) and isinstance(patch, dict):
        out = dict(base)
        for k, v in patch.items():
            if k in out and out.get(k) not in (None, "", [], {}, "unknown"):
                continue
            if v in (None, "", [], {}, "unknown") or (isinstance(v, str) and v.strip().lower() in {"unknown", "n/a", "na", "none", "null"}):
                continue
            out[k] = v
        return out
    if isinstance(base, list) and isinstance(patch, list):
        # If base is empty or a placeholder Unknown, accept patch.
        if not base or base == ["Unknown"]:
            return patch
        return base
    if isinstance(base, str) and base.strip().lower() in {"unknown", "n/a", "na", "none", "null"}:
        base = ""
    return base if base not in (None, "", "unknown") else patch


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