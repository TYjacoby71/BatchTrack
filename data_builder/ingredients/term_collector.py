"""AI-assisted collector that builds the seed ingredient queue and lookup forms."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import openai

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TERMS_FILE = BASE_DIR / "terms.json"
PHYSICAL_FORMS_FILE = OUTPUT_DIR / "physical_forms.json"
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    LOGGER.warning("OPENAI_API_KEY is not set; term_collector will run in repository-only mode unless --skip-ai is provided.")
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))
MAX_BATCH_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
DEFAULT_PRIORITY = 5
SEED_PRIORITY = 7
MIN_PRIORITY = 1
MAX_PRIORITY = 10

BASE_PHYSICAL_FORMS: Set[str] = {
    "Whole", "Slices", "Diced", "Chopped", "Minced", "Crushed", "Ground",
    "Powder", "Microfine Powder", "Granules", "Flakes", "Shreds", "Ribbons",
    "Pellets", "Chips", "Nib", "Buds", "Flowers", "Leaves", "Needles",
    "Stems", "Bark", "Resin", "Gum", "Latex", "Sap", "Juice", "Puree",
    "Paste", "Concentrate", "Syrup", "Molasses", "Infusion", "Decoction",
    "Tincture", "Hydrosol", "Essential Oil", "Absolute", "CO2 Extract",
    "Oleoresin", "Distillate", "Cold Pressed Oil", "Refined Oil", "Butter",
    "Wax", "Wafers", "Slab", "Block", "Sheet", "Beads", "Crystals",
    "Isolate", "Powdered Extract", "Spray-dried Powder", "Freeze-dried",
    "Dehydrated", "Whole Dried", "Roasted", "Toasted", "Smoke-dried",
    "Fermented", "Macerated", "Steeped", "Infused Oil", "Pressed Cake",
    "Expeller Cake", "Pomace", "Fiber", "Husk", "Hull", "Seed",
    "Kernel", "Nutmeat", "Flour", "Meal", "Starch", "Proteinate",
    "Chelated Powder", "Soluble Powder", "Emulsion", "Gel", "Jelly",
    "Glycerite", "Vinegar Extract", "Alcohol Extract", "Supercritical Extract"
}

EXAMPLE_INGREDIENTS: List[str] = [
    "Acacia Gum",
    "Activated Charcoal",
    "Agar Agar",
    "Alkanet Root",
    "Aloe Vera",
    "Apricot Kernel Oil",
    "Arrowroot Powder",
    "Beeswax",
    "Bentonite Clay",
    "Blue Cornflower",
    "Calendula",
    "Candelilla Wax",
    "Cane Sugar",
    "Cocoa Butter",
    "Coconut Oil",
    "Epsom Salt",
    "Gluconic Acid",
    "Glycerin",
    "Grapefruit Essential Oil",
    "Green Tea",
    "Honey Powder",
    "Jojoba Oil",
    "Kaolin Clay",
    "Kombucha Starter",
    "Lanolin",
    "Lavender",
    "Lye Solution (50% NaOH)",
    "Madder Root",
    "Magnesium Hydroxide",
    "Neem Oil",
    "Orange Peel",
    "Pink Himalayan Salt",
    "Potassium Carbonate Solution",
    "Propolis",
    "Rosemary Oleoresin",
    "Sassafras Bark",
    "Sea Buckthorn Pulp",
    "Shea Butter",
    "Sodium Bicarbonate",
    "Soy Lecithin",
    "Stearic Acid",
    "Tapioca Starch",
    "Turmeric",
    "Vanilla Bean",
    "White Willow Bark",
    "Witch Hazel Distillate",
    "Xanthan Gum",
    "Ylang Ylang Essential Oil",
    "Zinc Oxide",
]

EXAMPLE_PHYSICAL_FORMS: Set[str] = {
    "Essential Oil",
    "CO2 Extract",
    "Absolute",
    "Hydrosol",
    "Infusion",
    "Decoction",
    "Tincture",
    "Oil Infusion",
    "Pressed Cake",
    "Macreate",
    "Lye Solution",
    "Stock Solution",
}

SYSTEM_PROMPT = (
    "You are IngredientLibrarianGPT, a research assistant who curates canonical "
    "raw ingredients for small-batch makers across soap, cosmetic, confectionery, "
    "baking, beverage, herbal, aromatherapy, candle, and fermentation domains."
)

TERMS_PROMPT = """
You build the authoritative master ingredient index.

DEFINITIONS:
- An INGREDIENT (aka base) is the abstract raw material such as "Lavender", "Shea Butter", "Cane Sugar", "Citric Acid".
- An ITEM is the combination of INGREDIENT + PHYSICAL FORM (e.g., Lavender Buds, Lavender Essential Oil). ONLY return base ingredient names here.
- Focus on botanicals, minerals, clays, waxes, fats, sugars, acids, fermentation adjuncts, resins, essential oils, extracts, isolates, and other raw materials used by small-batch makers.
- EXCLUDE: packaging, containers, utensils, finished products, synthetic fragrances without a backing raw material, equipment, and vague marketing terms.

TASK:
Return a strictly alphabetical list of NEW base ingredient names that have not appeared previously. Every entry must be unique, discoverable in supplier catalogs, and relevant to at least one target industry: soapmaking, personal care, artisan food & beverage, herbal apothecary, candles, cosmetics, confectionery, or fermentation.

SOLUTION & EXTRACT GUIDANCE:
- Include buffered solutions, stock lye solutions (e.g., 50% NaOH), mineral brines, herbal glycerites, tinctures, vinegars, and other make-ready raw solutions when they are handled as ingredients.
- For botanicals with essential oils, hydrosols, absolutes, CO2 extracts, etc., treat the plant as the ingredient and enumerate those forms inside `common_forms`.
- Treat {count} as a minimum for this batch. If more valid ingredients exist beyond that count, KEEP ADDING them until you naturally reach the response limit. The overarching library will eventually exceed 5,000 and may reach 15,000+, so never intentionally leave alphabetical gaps.

For each ingredient, list the most common PHYSICAL FORMS (include essential oil/extract variants when applicable).

CONSTRAINTS:
- Provide AT LEAST {count} ingredient records (more is welcome if available).
- The first ingredient must be lexicographically GREATER than "{start_after}".
- Alphabetize A-Z.
- Avoid duplicates of the provided examples.
- Use concise proper names (e.g., "Calendula", "Magnesium Hydroxide").
- Assign a relevance score from 1-10 (integer) where 10 = essential for small-batch makers and 1 = niche or situational.
- If absolutely no valid ingredients remain, return an empty list.

OUTPUT FORMAT:
Return JSON only:
{{
  "ingredients": [
    {{
      "name": "string",
      "category": "one of: Botanical, Mineral, Animal-Derived, Fermentation, Chemical, Resin, Wax, Fatty Acid, Sugar, Acid, Salt, Aroma",
      "industries": ["Soap", "Cosmetic", "Candle", "Confection", "Beverage", "Herbal", "Baking", "Fermentation", "Aromatherapy"],
      "common_forms": ["Powder", "Essential Oil", ...],
      "notes": "1-sentence rationale",
      "priority_score": 1-10 integer (10 = highest relevance/urgency for makers)
    }}
  ],
  "physical_forms": ["unique physical forms referenced"]
}}

EXAMPLES TO EMULATE:
{examples}
"""


class TermCollector:
    """Coordinates local seeding, AI expansion, and output writing."""

    def __init__(
        self,
        target_count: int,
        batch_size: int,
        include_ai: bool = True,
        seed_root: Optional[Path] = None,
        example_file: Optional[Path] = None,
        terms_file: Optional[Path] = None,
    ) -> None:
        self.seed_root = seed_root if seed_root and seed_root.exists() else None
        self.target_count = target_count
        self.batch_size = batch_size
        self.include_ai = include_ai and bool(openai.api_key)
        self.terms: Dict[str, int] = {}
        self.physical_forms: Set[str] = set(BASE_PHYSICAL_FORMS) | EXAMPLE_PHYSICAL_FORMS
        self.prompt_examples: Set[str] = set(EXAMPLE_INGREDIENTS)
        if example_file and example_file.exists():
            try:
                data = json.loads(example_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    self.prompt_examples.update(str(item).strip() for item in data if str(item).strip())
            except json.JSONDecodeError:
                LOGGER.warning("Example file %s is not valid JSON; ignoring", example_file)

        # If a terms file already exists, load it so the collector can resume
        # from the last known term and avoid regenerating duplicates across runs.
        if terms_file:
            self.ingest_terms_file(terms_file)

    def _extract_priority(self, value) -> int:
        try:
            priority = int(value)
        except (TypeError, ValueError):
            priority = DEFAULT_PRIORITY
        return max(MIN_PRIORITY, min(MAX_PRIORITY, priority))

    def _register_term(self, term: str, priority: int) -> bool:
        """Track a term with the highest observed priority. Returns True if newly added."""
        cleaned = term.strip()
        if not cleaned:
            return False
        normalized_priority = self._extract_priority(priority)
        existing = self.terms.get(cleaned)
        if existing is None or normalized_priority > existing:
            self.terms[cleaned] = normalized_priority
            return existing is None
        return False

    def slugify(self, value: str) -> str:
        """
        Converts a string into a "slug".

        A slug is a readable, URL-friendly identifier.
        """
        value = str(value)
        value = re.sub(r'[^\w\s-]', '', value).strip().lower()
        value = re.sub(r'[-\s]+', '-', value)
        return value

    # ------------------------------------------------------------------
    # Existing term ingestion (ratchet persistence)
    # ------------------------------------------------------------------
    def ingest_terms_file(self, terms_file: Path) -> None:
        """Load an existing terms.json file to resume A→Z progression across runs."""
        try:
            if not terms_file.exists():
                return
            raw_text = terms_file.read_text(encoding="utf-8").strip()
            if not raw_text:
                return
            data = json.loads(raw_text)
            if not isinstance(data, list):
                LOGGER.warning("Terms file %s is not a JSON list; ignoring", terms_file)
                return
            loaded = 0
            for item in data:
                if isinstance(item, str):
                    term = item.strip()
                    if term and self._register_term(term, DEFAULT_PRIORITY):
                        loaded += 1
                    continue
                if isinstance(item, dict):
                    term = str(item.get("term") or item.get("name") or "").strip()
                    if not term:
                        continue
                    priority = item.get("priority") if "priority" in item else item.get("priority_score")
                    if self._register_term(term, priority):
                        loaded += 1
            if loaded:
                LOGGER.info("Loaded %s existing terms from %s", loaded, terms_file)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.warning("Failed to ingest existing terms from %s: %s", terms_file, exc)

    # ------------------------------------------------------------------
    # Seed extraction
    # ------------------------------------------------------------------
    def ingest_seed_directory(self) -> None:
        if not self.seed_root:
            LOGGER.info("No seed directory supplied; relying entirely on AI generation.")
            return

        for json_path in self.seed_root.rglob("*.json"):
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                LOGGER.debug("Skipping non-JSON file %s", json_path)
                continue
            self._collect_from_obj(data)

        LOGGER.info("Loaded %s seed terms from %s", len(self.terms), self.seed_root)

    def _collect_from_obj(self, obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == "category_name":
                    continue
                if key in {"name", "common_name", "ingredient_name"} and isinstance(value, str):
                    cleaned = value.strip()
                    if cleaned:
                        self._register_term(cleaned, SEED_PRIORITY)
                if key == "ingredient" and isinstance(value, dict):
                    name = value.get("name")
                    if isinstance(name, str) and name.strip():
                        self._register_term(name.strip(), SEED_PRIORITY)
                if key == "physical_form" and isinstance(value, str):
                    self.physical_forms.add(value.strip())
                self._collect_from_obj(value)
        elif isinstance(obj, list):
            for item in obj:
                self._collect_from_obj(item)

    # ------------------------------------------------------------------
    # AI Expansion
    # ------------------------------------------------------------------
    def expand_with_ai(self) -> None:
        if not self.include_ai:
            LOGGER.warning("OPENAI_API_KEY missing; skipping AI term generation")
            return

        while len(self.terms) < self.target_count:
            start_after = sorted(self.terms.keys())[-1] if self.terms else ""
            batch_size = min(self.batch_size, self.target_count - len(self.terms))
            LOGGER.info(
                "Requesting %s new terms after '%s' (current total: %s/%s)",
                batch_size,
                start_after or "<start>",
                len(self.terms),
                self.target_count,
            )
            examples = self._compose_examples(24)
            payload = self._request_ai_batch(batch_size, start_after, examples)
            if not payload:
                LOGGER.warning("AI returned no payload; breaking out")
                break
            new_terms = 0
            for record in payload.get("ingredients", []):
                name = record.get("name")
                if not isinstance(name, str):
                    continue
                cleaned = name.strip()
                if not cleaned:
                    continue
                priority = record.get("priority_score")
                if self._register_term(cleaned, priority):
                    new_terms += 1
                for form in record.get("common_forms", []) or []:
                    if isinstance(form, str) and form.strip():
                        self.physical_forms.add(form.strip())
            for form in payload.get("physical_forms", []) or []:
                if isinstance(form, str) and form.strip():
                    self.physical_forms.add(form.strip())
            LOGGER.info("Ingested %s brand-new ingredients", new_terms)
            if new_terms == 0:
                break

    def _compose_examples(self, limit: int) -> List[str]:
        live_samples = sorted(self.terms.keys())[: limit // 2]
        curated = sorted(self.prompt_examples)[: limit - len(live_samples)]
        combined = curated + live_samples
        return combined[:limit]

    def _request_ai_batch(self, count: int, start_after: str, examples: List[str]) -> Dict[str, Any]:
        user_prompt = TERMS_PROMPT.format(
            count=count,
            start_after=start_after.replace("\"", ""),
            examples=json.dumps(examples, indent=2) if examples else "[]",
        )

        client = openai.OpenAI(api_key=openai.api_key)

        for attempt in range(1, MAX_BATCH_RETRIES + 1):
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
                    raise ValueError("AI payload is not a JSON object")
                return payload
            except json.JSONDecodeError as exc:
                LOGGER.warning("JSON decode failed for attempt %s. Raw content (first 200 chars): %s", attempt, content[:200] if 'content' in locals() else "No content available")
                LOGGER.warning("JSON decode error: %s", exc)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.warning("Term generation attempt %s failed: %s", attempt, exc)
        return {}

    # ------------------------------------------------------------------
    # Outputs
    # ------------------------------------------------------------------
    def write_terms_file(self, path: Path = TERMS_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            {"term": term, "priority": priority}
            # IMPORTANT: `terms.json` is the canonical master list and must be
            # strict lexicographic order (A→Z, with punctuation like '.' first).
            # Priority is metadata for the compiler, not an ordering dimension here.
            for term, priority in sorted(self.terms.items(), key=lambda item: (item[0].casefold(), item[0]))
        ]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        LOGGER.info("Wrote %s terms to %s", len(payload), path)

    def write_forms_file(self, path: Path = PHYSICAL_FORMS_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(self.physical_forms)
        path.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
        LOGGER.info("Wrote %s physical forms to %s", len(ordered), path)

    


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the ingredient term queue via local + AI sources")
    parser.add_argument("--seed-root", default="", help="Optional directory to scan for seed data (leave blank to skip)")
    parser.add_argument("--example-file", default="", help="Optional JSON array of canonical example ingredients for prompt context")
    parser.add_argument("--target-count", type=int, default=5000, help="Desired total number of base ingredients")
    parser.add_argument("--batch-size", type=int, default=250, help="AI batch size per request")
    parser.add_argument("--terms-file", default=str(TERMS_FILE), help="Destination JSON file for term list (term + priority)")
    parser.add_argument("--forms-file", default=str(PHYSICAL_FORMS_FILE), help="Destination file for physical forms list")
    parser.add_argument("--skip-ai", action="store_true", help="Only use repo seeds; do not call the AI API")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(
        level=os.getenv("COMPILER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = parse_args(argv)

    collector = TermCollector(
        target_count=args.target_count,
        batch_size=args.batch_size,
        include_ai=not args.skip_ai,
        seed_root=Path(args.seed_root).resolve() if args.seed_root else None,
        example_file=Path(args.example_file).resolve() if args.example_file else None,
        terms_file=Path(args.terms_file).resolve() if args.terms_file else None,
    )

    collector.ingest_seed_directory()
    collector.expand_with_ai()
    collector.write_terms_file(Path(args.terms_file))
    collector.write_forms_file(Path(args.forms_file))


if __name__ == "__main__":
    main()