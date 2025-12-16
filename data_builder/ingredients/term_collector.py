"""AI-assisted collector that builds the seed ingredient queue and lookup forms."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import openai

LOGGER = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TERMS_FILE = BASE_DIR / "terms.json"
PHYSICAL_FORMS_FILE = OUTPUT_DIR / "physical_forms.json"
TERM_STUBS_DIR = OUTPUT_DIR / "term_stubs"
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
DEFAULT_CANDIDATE_POOL_SIZE = int(os.getenv("TERM_GENERATOR_CANDIDATE_POOL", "30"))
MAX_SELECTION_ATTEMPTS = int(os.getenv("TERM_GENERATOR_SELECTION_ATTEMPTS", "12"))
MAX_CANDIDATE_POOL_SIZE = int(os.getenv("TERM_GENERATOR_MAX_CANDIDATE_POOL", "120"))
# Optional: sample additional AI candidate pools with category hints to increase recall
# (helps close "gaps" at the cost of extra API calls).
CATEGORY_HINTS_PER_ATTEMPT = int(os.getenv("TERM_GENERATOR_CATEGORY_HINTS_PER_ATTEMPT", "0"))
CATEGORY_HINT_POOL_SIZE = int(os.getenv("TERM_GENERATOR_CATEGORY_HINT_POOL_SIZE", "10"))

REPO_ROOT = BASE_DIR.parent.parent
SEED_CATEGORY_DIR = REPO_ROOT / "app" / "seeders" / "globallist" / "ingredients" / "categories"


def _load_category_hints() -> List[str]:
    """Load canonical ingredient category names from seed files (preferred)."""
    hints: List[str] = []

    if SEED_CATEGORY_DIR.exists():
        for path in sorted(SEED_CATEGORY_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # pylint: disable=broad-except
                continue
            if not isinstance(data, dict):
                continue
            name = str(data.get("category_name") or "").strip()
            if name:
                hints.append(name)

    # Fallback to builder/compiler categories if seed files aren't present.
    if not hints:
        try:  # pragma: no cover - best effort, avoids hard dependency
            from .ai_worker import INGREDIENT_CATEGORIES as fallback  # type: ignore
        except Exception:  # pragma: no cover
            fallback = []
        hints.extend([str(item).strip() for item in (fallback or []) if str(item).strip()])

    # Deterministic, unique ordering.
    deduped = sorted({hint for hint in hints if hint})
    return deduped


CATEGORY_HINTS: List[str] = _load_category_hints()

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
    "Arrowroot",
    "Beeswax",
    "Bentonite Clay",
    "Cornflower",
    "Calendula",
    "Candelilla Wax",
    "Cane Sugar",
    "Cocoa Butter",
    "Coconut Oil",
    "Epsom Salt",
    "Gluconic Acid",
    "Glycerin",
    "Grapefruit",
    "Green Tea",
    "Honey",
    "Jojoba Oil",
    "Kaolin Clay",
    "Kombucha Starter",
    "Lanolin",
    "Lavender",
    "Sodium Hydroxide",
    "Madder Root",
    "Magnesium Hydroxide",
    "Neem Oil",
    "Orange",
    "Pink Himalayan Salt",
    "Potassium Carbonate",
    "Propolis",
    "Rosemary",
    "Sassafras Bark",
    "Sea Buckthorn",
    "Shea Butter",
    "Sodium Bicarbonate",
    "Soy Lecithin",
    "Stearic Acid",
    "Tapioca Starch",
    "Turmeric",
    "Vanilla Bean",
    "White Willow Bark",
    "Witch Hazel",
    "Xanthan Gum",
    "Ylang Ylang",
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
    "Macerate",
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
- An INGREDIENT (aka base) is the canonical purchasable raw material name you would index in a supplier catalog such as "Lavender", "Shea Butter", "Cane Sugar", "Citric Acid", "Apple Juice", "Applesauce", "Oat Milk".
- An ITEM is the combination of INGREDIENT + PHYSICAL FORM (e.g., Lavender Buds, Lavender Essential Oil).
- IMPORTANT: ONLY return base ingredient names in `ingredients[].name`. NEVER return a physical form / preparation as the base name.
- Focus on botanicals, minerals, clays, waxes, fats, sugars, acids, fermentation adjuncts, resins, essential oils, extracts, isolates, and other raw materials used by small-batch makers.
- EXCLUDE: packaging, containers, utensils, finished products, synthetic fragrances without a backing raw material, equipment, and vague marketing terms.

TASK:
Return a strictly alphabetical list of NEW base ingredient names that have not appeared previously. Every entry must be unique, discoverable in supplier catalogs, and relevant to at least one target industry: soapmaking, personal care, artisan food & beverage, herbal apothecary, candles, cosmetics, confectionery, or fermentation.

CATEGORY FOCUS (OPTIONAL):
- If `category_hint` is provided, prefer bases commonly sold under that broad supplier category.
- `category_hint` is only a search hint. The output `category` field must still be chosen from the allowed enum.

SOLUTION & EXTRACT GUIDANCE:
- Solutions, extracts, distillates, isolates, essential oils, hydrosols, absolutes, CO2 extracts, glycerites, tinctures, infusions, decoctions, vinegars, and other preparations are PHYSICAL FORMS.
- If a candidate name is a preparation/form (e.g., "Acerola Extract", "Witch Hazel Distillate", "Lavender Essential Oil", "Sodium Hydroxide 50% Solution"), do NOT add it as a base; instead, treat it as a `common_forms` entry for the appropriate base and choose a different new base name.
- For botanicals with essential oils/hydrosols/absolutes/CO2 extracts, treat the plant as the ingredient and enumerate those preparations inside `common_forms`.
- Fixed oils/butters/waxes are valid bases as written (e.g., "Olive Oil", "Shea Butter", "Beeswax") and should still list their refinements in `common_forms` (e.g., "Refined", "Unrefined", "Bleached", "Deodorized").

For each ingredient, list the most common PHYSICAL FORMS in `common_forms` (Powder, Whole, Juice, Concentrate, Oil, Butter, Wax, etc.).
Note: labeling/grade variations (e.g., 2%, raw, filtered, unsweetened) are handled downstream by the compiler; do not output a separate variations list here.

CONSTRAINTS:
- Provide EXACTLY {count} ingredient records.
- Every ingredient name MUST start with "{required_initial}" (case-insensitive).
- Every ingredient name MUST be lexicographically GREATER than "{start_after}".
- Alphabetize A-Z within the response.
- Avoid duplicates of the provided examples.
- Use concise proper names (e.g., "Calendula", "Magnesium Hydroxide").
- Assign a relevance score from 1-10 (integer) where 10 = essential for small-batch makers and 1 = niche or situational.
- If no valid ingredients remain under the constraints, return an empty list.

OUTPUT FORMAT:
Return JSON only:
{{
  "category_hint_used": "string | null",
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
- Good base vs bad base:
  - Good: "Acerola Cherry" with common_forms: ["Whole Dried", "Powder", "Extract", "Juice"]
  - Bad: "Acerola Extract" as a separate base name (this must be a form under "Acerola Cherry")
  - Good: "Apple Juice" (base) with common_forms: ["Juice", "Concentrate"]
  - Good: "Oat Milk" (base) with common_forms: ["Liquid"]
{examples}
"""


# ------------------------------------------------------------------
# Term validation / de-dup (defense-in-depth against "forms as bases")
# ------------------------------------------------------------------
_FORM_LIKE_PATTERNS: Tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, flags=re.IGNORECASE)
    for pattern in (
        r"\bessential\s+oil\b",
        r"\bhydrosol\b",
        r"\babsolute\b",
        r"\bco2\b",
        r"\boleoresin\b",
        r"\bdistillate\b",
        r"\btincture\b",
        r"\bglycerite\b",
        r"\binfusion\b",
        r"\bdecoction\b",
        r"\bmacerat(?:e|ion)\b",
        r"\bextract\b",
        r"\bisolate\b",
        r"\bsolution\b",
        r"\bbrine\b",
        r"\b\d+(\.\d+)?\s*%\b",
        # Variation-ish adjectives that should not appear as standalone bases.
        r"\bgranulated\b",
        r"\bpowdered\b",
        r"\brefined\b",
        r"\bunrefined\b",
        r"\bdeodorized\b",
        r"\bfiltered\b",
        r"\bunfiltered\b",
        r"\bunsweetened\b",
        r"\bsweetened\b",
    )
)


def _looks_like_form_not_base(term: str) -> bool:
    """Return True if `term` appears to be a prepared form (not a canonical base)."""
    cleaned = (term or "").strip()
    if not cleaned:
        return True
    # Avoid "X (something)" style variants at the term level; those belong in items/synonyms.
    if "(" in cleaned or ")" in cleaned:
        return True
    return any(pattern.search(cleaned) for pattern in _FORM_LIKE_PATTERNS)


def _select_category_hints(initial: str, start_after: str, limit: int) -> List[str]:
    """Choose a stable rotating subset of CATEGORY_HINTS for this cursor."""
    limit = max(0, int(limit or 0))
    if limit == 0 or not CATEGORY_HINTS:
        return []
    # Stable seed so repeated runs for same cursor rotate predictably.
    seed = f"{(initial or '').upper()}|{(start_after or '').casefold()}"
    digest = int(hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8], 16)
    start_idx = digest % len(CATEGORY_HINTS)
    ordered = CATEGORY_HINTS[start_idx:] + CATEGORY_HINTS[:start_idx]
    return ordered[: min(limit, len(ordered))]


class TermCollector:
    """Coordinates local seeding, AI expansion, and output writing."""

    def __init__(
        self,
        include_ai: bool = True,
        seed_root: Optional[Path] = None,
        example_file: Optional[Path] = None,
        terms_file: Optional[Path] = None,
        seed_from_db: bool = True,
    ) -> None:
        self.seed_root = seed_root if seed_root and seed_root.exists() else None
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

        # Prefer the queue DB as the true source-of-truth for resuming across runs.
        if seed_from_db:
            self.ingest_terms_from_db()

        # Never regress lookup files: if a physical forms file already exists (likely enriched
        # by the compiler), merge it in so a subsequent --write-forms-file doesn't wipe it.
        self._ingest_existing_forms_file(PHYSICAL_FORMS_FILE)

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

    def _term_file_key(self, term: str) -> str:
        """Stable per-term file key to avoid collisions."""
        base = re.sub(r"[^a-zA-Z0-9]+", "_", term.lower()).strip("_") or "term"
        digest = hashlib.sha1(term.encode("utf-8")).hexdigest()[:8]  # deterministic, short
        return f"{base}_{digest}"

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

    def ingest_terms_from_db(self) -> None:
        """Load existing terms from the compiler queue DB (preferred persistence layer)."""
        try:
            from . import database_manager
        except Exception:  # pragma: no cover
            return

        try:
            existing = database_manager.get_all_terms()
            for term, priority in existing:
                self._register_term(term, priority)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("Skipping DB term ingestion: %s", exc)

    # ------------------------------------------------------------------
    # Seed extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _is_under(path: Path, base: Path) -> bool:
        """Return True if path is within base (best-effort, cross-version)."""
        try:
            path.resolve().relative_to(base.resolve())
            return True
        except Exception:
            return False

    def ingest_seed_directory(self) -> None:
        if not self.seed_root:
            LOGGER.info("No seed directory supplied; relying entirely on AI generation.")
            return

        for json_path in self.seed_root.rglob("*.json"):
            # Stage 1 must not ingest stage 2 outputs (compiled ingredient files / lookups).
            if self._is_under(json_path, OUTPUT_DIR):
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                LOGGER.debug("Skipping non-JSON file %s", json_path)
                continue
            self._collect_from_obj(data)

        LOGGER.info("Loaded %s seed terms from %s", len(self.terms), self.seed_root)

    def _ingest_existing_forms_file(self, path: Path) -> None:
        """Merge an existing physical_forms.json list into the in-memory set."""
        try:
            if not path.exists():
                return
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                return
            data = json.loads(raw)
            if not isinstance(data, list):
                return
            for item in data:
                if isinstance(item, str) and item.strip():
                    self.physical_forms.add(item.strip())
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("Skipping existing forms file ingest (%s): %s", path, exc)

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
    def _iter_ai_candidates(
        self,
        *,
        start_after: str,
        required_initial: str,
        count: int,
        examples: List[str],
        category_hint: Optional[str] = None,
    ) -> List[Tuple[str, int]]:
        """Request a small candidate pool from the AI and return (term, priority) tuples."""
        payload = self._request_ai_batch(
            count=count,
            start_after=start_after,
            required_initial=required_initial,
            examples=examples,
            category_hint=category_hint,
        )
        if not payload:
            return []
        out: List[Tuple[str, int]] = []
        for record in payload.get("ingredients", []) or []:
            name = record.get("name")
            if not isinstance(name, str):
                continue
            cleaned = name.strip()
            if not cleaned:
                continue
            priority = self._extract_priority(record.get("priority_score"))
            out.append((cleaned, priority))
            for form in record.get("common_forms", []) or []:
                if isinstance(form, str) and form.strip():
                    self.physical_forms.add(form.strip())
        for form in payload.get("physical_forms", []) or []:
            if isinstance(form, str) and form.strip():
                self.physical_forms.add(form.strip())
        return out

    def _select_next_term(
        self,
        *,
        start_after: str,
        required_initial: str,
        candidate_pool_size: int,
    ) -> Optional[Tuple[str, int]]:
        """Ask the AI for candidates and select the next viable lexicographic term."""
        selected: Optional[Tuple[str, int]] = None
        start_fold = (start_after or "").casefold()
        req_fold = (required_initial or "").strip()[:1].casefold()
        if not req_fold:
            return None

        attempts = 0
        pool_size = max(5, min(int(candidate_pool_size or DEFAULT_CANDIDATE_POOL_SIZE), MAX_CANDIDATE_POOL_SIZE))
        while selected is None and attempts < MAX_SELECTION_ATTEMPTS:
            attempts += 1
            # Ramp pool size a bit if we're failing to find a viable term.
            candidate_count = min(MAX_CANDIDATE_POOL_SIZE, max(5, pool_size + (attempts - 1) * 10))
            examples = self._compose_examples(24)
            candidates: List[Tuple[str, int]] = []
            # Baseline, uncategorized candidate pool.
            candidates.extend(self._iter_ai_candidates(
                start_after=start_after,
                required_initial=req_fold.upper(),
                count=candidate_count,
                examples=examples,
                category_hint=None,
            ))

            # Optional: add a few small category-hinted pools to improve recall and reduce gaps.
            per_attempt = max(0, int(CATEGORY_HINTS_PER_ATTEMPT or 0))
            if per_attempt:
                hints = _select_category_hints(required_initial, start_after, per_attempt)
                hinted_count = max(5, min(int(CATEGORY_HINT_POOL_SIZE or 10), MAX_CANDIDATE_POOL_SIZE))
                for hint in hints:
                    candidates.extend(self._iter_ai_candidates(
                        start_after=start_after,
                        required_initial=req_fold.upper(),
                        count=hinted_count,
                        examples=examples,
                        category_hint=hint,
                    ))

            viable: List[Tuple[str, int]] = []
            for term, priority in candidates:
                if term.casefold() <= start_fold:
                    continue
                if term[:1].casefold() != req_fold:
                    continue
                if _looks_like_form_not_base(term):
                    continue
                if term in self.terms:
                    continue
                viable.append((term, priority))

            if viable:
                viable.sort(key=lambda item: (item[0].casefold(), item[0]))
                selected = viable[0]

        return selected

    def seed_next_terms_to_db(
        self,
        *,
        count: int,
        candidate_pool_size: int = DEFAULT_CANDIDATE_POOL_SIZE,
    ) -> int:
        """Stage 1: Generate NEW terms and upsert each one immediately into the DB.

        This builder is intentionally single-mode: round-robin by letter category.

        It generates the next term for A, then B, then C ... through Z, repeating.
        Each step uses the DB as the source-of-truth for the per-letter cursor.
        """
        if not self.include_ai:
            LOGGER.warning("OPENAI_API_KEY missing; skipping AI term generation")
            return 0

        try:
            from . import database_manager
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("DB manager unavailable; cannot seed queue DB: %s", exc)
            return 0

        inserted = 0
        normalized_count = max(0, int(count or 0))
        if normalized_count == 0:
            return 0

        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        for idx in range(normalized_count):
            initial = letters[idx % len(letters)]
            start_after = database_manager.get_last_term_for_initial(initial) or ""
            selected = self._select_next_term(
                start_after=start_after,
                required_initial=initial,
                candidate_pool_size=candidate_pool_size,
            )
            if selected is None:
                LOGGER.warning(
                    "Unable to find next term for '%s' after '%s' on iteration %s/%s",
                    initial,
                    start_after or "<start>",
                    idx + 1,
                    normalized_count,
                )
                break

            term, priority = selected
            was_inserted = database_manager.upsert_term(term, priority)
            self._register_term(term, priority)
            if was_inserted:
                inserted += 1
                LOGGER.info("Queued term %s/%s: %s (priority=%s)", idx + 1, normalized_count, term, priority)

        return inserted

    def _compose_examples(self, limit: int) -> List[str]:
        live_samples = sorted(self.terms.keys())[: limit // 2]
        curated = sorted(self.prompt_examples)[: limit - len(live_samples)]
        combined = curated + live_samples
        return combined[:limit]

    def _request_ai_batch(
        self,
        *,
        count: int,
        start_after: str,
        required_initial: str,
        examples: List[str],
        category_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        user_prompt = TERMS_PROMPT.format(
            count=count,
            start_after=start_after.replace("\"", ""),
            required_initial=(required_initial or "").replace("\"", ""),
            examples=json.dumps(examples, indent=2) if examples else "[]",
        )
        if category_hint:
            user_prompt = f"{user_prompt}\n\ncategory_hint: {category_hint}\n"

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
        # Merge on-disk file (if any) to avoid wiping compiler-enriched values.
        self._ingest_existing_forms_file(path)
        ordered = sorted(self.physical_forms)
        path.write_text(json.dumps(ordered, indent=2), encoding="utf-8")
        LOGGER.info("Wrote %s physical forms to %s", len(ordered), path)

    def write_term_stubs(self, directory: Path = TERM_STUBS_DIR) -> None:
        """Write one small JSON stub per term (avoids a single giant terms.json)."""
        directory.mkdir(parents=True, exist_ok=True)
        for term, priority in self.terms.items():
            key = self._term_file_key(term)
            path = directory / f"{key}.json"
            payload = {
                "term": term,
                "priority": int(priority),
                "status": "pending",
            }
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        LOGGER.info("Wrote %s term stubs to %s", len(self.terms), directory)

    def seed_queue_db(self) -> int:
        """Upsert all known terms into the compiler queue database."""
        try:
            from . import database_manager
        except Exception:  # pragma: no cover
            return 0
        return database_manager.upsert_terms(self.terms.items())

    


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the ingredient term queue via local + AI sources")
    parser.add_argument("--seed-root", default="", help="Optional directory to scan for seed data (leave blank to skip)")
    parser.add_argument("--ingest-seeds", action="store_true", help="If set, scan --seed-root for seed terms (output/ is always ignored)")
    parser.add_argument("--example-file", default="", help="Optional JSON array of canonical example ingredients for prompt context")
    parser.add_argument("--count", type=int, default=250, help="How many NEW alphabetical terms to create and queue now")
    parser.add_argument("--candidate-pool", type=int, default=DEFAULT_CANDIDATE_POOL_SIZE, help="Internal AI candidate pool size (kept small; not a DB batch)")
    parser.add_argument("--skip-ai", action="store_true", help="Only use repo seeds; do not call the AI API")
    parser.add_argument("--write-forms-file", action="store_true", help="Write the physical_forms.json output (optional)")
    parser.add_argument("--forms-file", default=str(PHYSICAL_FORMS_FILE), help="Destination file for physical forms list")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(
        level=os.getenv("COMPILER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    args = parse_args(argv)

    collector = TermCollector(
        include_ai=not args.skip_ai,
        seed_root=Path(args.seed_root).resolve() if args.seed_root else None,
        example_file=Path(args.example_file).resolve() if args.example_file else None,
        terms_file=None,
    )

    # Optional seed ingestion (never reads stage-2 output/ files).
    if args.ingest_seeds:
        collector.ingest_seed_directory()
        if collector.terms:
            collector.seed_queue_db()

    # Then generate next alphabetical terms, committing each immediately.
    collector.seed_next_terms_to_db(
        count=max(0, int(args.count or 0)),
        candidate_pool_size=max(5, int(args.candidate_pool or DEFAULT_CANDIDATE_POOL_SIZE)),
    )

    if args.write_forms_file:
        collector.write_forms_file(Path(args.forms_file))


if __name__ == "__main__":
    main()