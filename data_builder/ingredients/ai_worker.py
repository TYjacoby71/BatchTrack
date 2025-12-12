"""OpenAI worker responsible for fetching structured ingredient data."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict

import openai

LOGGER = logging.getLogger(__name__)

openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    LOGGER.warning("OPENAI_API_KEY is not set; ai_worker will fail until configured.")

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.1"))
MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
RETRY_BACKOFF_SECONDS = float(os.getenv("AI_RETRY_BACKOFF", "3"))

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
    "manufacturing. You only output JSON that conforms to the provided schema."
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
        "physical_form": "choose from common forms such as Butter, Powder, Chips, Pellets, Granules, Crystals, Oil, Resin, Wax, Paste, Slab, Whole, Slices, Shavings, Ribbon, Nibs, Shreds, Flakes, Gel, Puree, Juice, Concentrate, Syrup",
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
          "ph_range": {"min": 5, "max": 7},
          "usage_rate_percent": {"leave_on_max": 5, "rinse_off_max": 15}
        },
        "sourcing": {
          "common_origins": ["Ghana", "Ivory Coast"],
          "certifications": ["Organic", "Fair Trade"],
          "supply_risks": ["Seasonal Harvest"],
          "sustainability_notes": "Tree nut resource"
        },
        "form_bypass": true | false  // when true, display should use item_name alone (e.g., Water, Ice)
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
- For each ingredient, enumerate every common PHYSICAL FORM (solid, powder, puree, resin, etc.) used in craft production. Create a dedicated `items` entry for every form.
- Populate every applicable attribute in the schema. Use "unknown" only when absolutely no data exists.
- Use authoritative references (USP, FCC, cosmetic suppliers, herbal materia medica) when citing specs.
- Use metric units. Shelf life must be expressed in DAYS (convert from months/years when needed). Temperature in Celsius.
- All string values must be clear, sentence case, and free of marketing fluff.
- Return strictly valid JSON (UTF-8, double quotes, no trailing commas). If you are uncertain, respond with {"error": "explanation"}.

CONTROLLED VOCAB REMINDERS:
- physical_form must be a short noun (e.g., "Powder", "Chips", "Pellets", "Whole", "Puree", "Pressed Cake").
- function_tags should draw from: Emollient, Humectant, Surfactant, Emulsifier, Preservative, Antioxidant, Colorant, Fragrance, Exfoliant, Thickener, Binder, Fuel, Hardener, Stabilizer, Plasticizer, Chelator, Buffer, Flavor, Sweetener, Bittering Agent, Fermentation Nutrient.
- applications should be chosen from: Cold Process Soap, Hot Process Soap, Melt & Pour Soap, Lotion, Cream, Balm, Serum, Scrub, Perfume, Candle, Wax Melt, Lip Balm, Chocolate, Confection, Baked Good, Beverage, Fermented Beverage, Herbal Tincture, Hydro-distillation, Bath Bomb, Shower Steamer, Haircare, Skincare, Deodorant, Cleaner, Detergent, Paint, Dye Bath.
- ingredient.category must be one of: {categories}

FORM & SOLUTION GUIDANCE:
- Always include dairy variants (e.g., whole milk, 2% milk, skim milk powder) and note their distinct forms.
- Include buffered/stock solutions (e.g., 50% Sodium Hydroxide Solution, 20% Potassium Carbonate Solution) when common in production.
- Essential oils, hydrosols, absolutes, CO2 extracts, glycerites, tinctures, macerations, and infusions should be represented as distinct forms under the parent ingredient.
- When an ingredient should display without a suffix (Water, Ice, Steam), set `form_bypass`=true so the interface shows just "Water" or "Ice" while still recording the underlying physical_form.
- When no better industry name exists, use a concise solution label such as "Potassium Carbonate Solution (20%)" or simply "Brine Solution".

SCHEMA (required):
{schema}

OUTPUT CONTRACT:
- Respond with a single JSON object adhering to the schema.
- If ingredient is out of scope or data unavailable, return {error_object} with a precise message.
"""


def _render_prompt(ingredient_name: str) -> str:
    return PROMPT_TEMPLATE.format(
        ingredient=ingredient_name.strip(),
        schema=JSON_SCHEMA_SPEC,
        error_object=json.dumps(ERROR_OBJECT),
        categories=", ".join(INGREDIENT_CATEGORIES),
    )


def get_ingredient_data(ingredient_name: str) -> Dict[str, Any]:
    """Fetch structured data for a single ingredient via the OpenAI API."""

    if not ingredient_name or not ingredient_name.strip():
        raise ValueError("ingredient_name is required")

    if not openai.api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not configured")

    user_prompt = _render_prompt(ingredient_name)
    last_error: Exception | None = None

    client = openai.OpenAI(api_key=openai.api_key)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                temperature=TEMPERATURE,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content = response.choices[0].message.content
            if not content or not content.strip():
                raise ValueError("OpenAI returned empty response content")
            
            content = content.strip()
            LOGGER.debug("OpenAI response content: %s", content[:200] + "..." if len(content) > 200 else content)
            
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("AI response was not a JSON object")
            return payload
        except json.JSONDecodeError as exc:
            last_error = exc
            LOGGER.warning("JSON decoding failed for %s (attempt %s): %s", ingredient_name, attempt, exc)
            LOGGER.warning("Raw content (first 200 chars): %s", content[:200] if 'content' in locals() else "No content available")
        except Exception as exc:  # pylint: disable=broad-except
            last_error = exc
            LOGGER.warning("OpenAI call failed for %s (attempt %s): %s", ingredient_name, attempt, exc)

        time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    error_message = (
        f"Failed to compile ingredient '{ingredient_name}' after {MAX_RETRIES} attempts: {last_error}"
    )
    LOGGER.error(error_message)
    return {"error": error_message}
