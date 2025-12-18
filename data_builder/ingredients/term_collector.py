"""AI-assisted collector that builds the seed ingredient queue (stage 1)."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import hashlib
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import openai

LOGGER = logging.getLogger(__name__)

# Centralized path layout (supports both module and direct script execution).
try:  # pragma: no cover
    from data_builder import paths as builder_paths  # type: ignore
except Exception:  # pragma: no cover
    builder_paths = None  # type: ignore

if builder_paths is not None:
    builder_paths.ensure_layout()
    OUTPUT_DIR = builder_paths.OUTPUTS_DIR
    TERMS_FILE = builder_paths.TERMS_FILE
    PHYSICAL_FORMS_FILE = builder_paths.PHYSICAL_FORMS_FILE
    TERM_STUBS_DIR = builder_paths.TERM_STUBS_DIR
    DATA_SOURCES_DIR = builder_paths.DATA_SOURCES_DIR
else:
    BUILDER_ROOT = Path(__file__).resolve().parents[1]
    OUTPUT_DIR = BUILDER_ROOT / "outputs"
    TERMS_FILE = BUILDER_ROOT / "data_sources" / "terms.json"
    PHYSICAL_FORMS_FILE = OUTPUT_DIR / "physical_forms.json"
    TERM_STUBS_DIR = OUTPUT_DIR / "term_stubs"
    DATA_SOURCES_DIR = BUILDER_ROOT / "data_sources"
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
# Stage 1 cursor mode:
# - legacy: per-letter cursor (A..Z)
# - category cursor: per-(seed_category, letter) cursor
USE_CATEGORY_CURSOR = os.getenv("TERM_GENERATOR_USE_CATEGORY_CURSOR", "1").strip() not in {"0", "false", "False"}
USE_SOURCE_TERMS = os.getenv("TERM_GENERATOR_USE_SOURCE_TERMS", "1").strip() not in {"0", "false", "False"}
INGEST_SOURCE_TERMS = os.getenv("TERM_GENERATOR_INGEST_SOURCE_TERMS", "0").strip() in {"1", "true", "True"}
TERM_GENERATOR_MODE = os.getenv("TERM_GENERATOR_MODE", "gapfill").strip().lower()
GAPFILL_MAX_TRIES_PER_LETTER = int(os.getenv("TERM_GENERATOR_GAPFILL_MAX_TRIES", "5"))

# Canonical base-level categories (hard-coded; Stage 1 cursor is (seed_category, letter)).
# IMPORTANT: these categories are "pure bases" (avoid base+form names like "Frankincense Resin").
SEED_INGREDIENT_CATEGORIES: List[str] = [
    "Fruits & Berries",
    "Vegetables",
    "Grains",
    "Nuts",
    "Seeds",
    "Spices",
    "Culinary Herbs",
    "Medicinal Herbs",
    "Flowers",
    "Roots",
    "Barks",
    "Sugars",
    "Liquid Sweeteners",
    "Acids",
    "Salts",
    "Minerals",
    "Clays",
    "Plants for Oils",
    "Plants for Butters",
    "Waxes",
    "Resins",
    "Gums",
    "Colorants",
    "Fermentation Starters",
]

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
You are running Stage 1 (Term Builder). Your ONLY job is to propose NEW base ingredient terms.

DEFINITIONS (Stage 1):
- A BASE INGREDIENT TERM is the canonical base name (usually 1–2 words) used to group purchasable items and their variants.
- The base is typically the plant/mineral/salt/sugar/acid/clay/etc. root name (e.g., "Apple", "Acerola Cherry", "Cinnamon", "Frankincense", "Kaolin", "Citric Acid").
- Do NOT output base+form names for these categories:
  - Resins: output "Frankincense", NOT "Frankincense Resin"
  - Plants for Oils: output "Cinnamon", NOT "Cinnamon Essential Oil"
  - Plants for Butters: output "Shea", NOT "Shea Butter"
- Do NOT output preparations/forms/variants as base terms (e.g., "Extract", "Essential Oil", "CO2 Extract", "Hydrosol", "% Solution", "Granulated", "2%").

TARGET CURSOR:
- seed_category: "{seed_category}"
- required_initial: "{required_initial}" (case-insensitive)
- start_after: "{start_after}"

TASK:
Return EXACTLY {count} NEW base ingredient terms for the given seed_category that:
- start with required_initial
- are lexicographically GREATER than start_after
- are strictly alphabetized A→Z in the response

IMPORTANT (NEXT-TERM INTENT):
- Prefer the *very next* alphabetical base ingredient(s) in this seed_category after start_after.
- If you are unsure of the exact next term, return the closest plausible next terms without skipping far ahead.

STYLE RULES:
- Use concise proper names; avoid descriptors like "organic", "raw", "powder", "oil", "extract", "resin".
- Multi-word is allowed when needed (e.g., "Sea Buckthorn", "Pink Himalayan Salt", "Marshmallow Root").
- Never include parentheticals.

OUTPUT FORMAT:
Return JSON only:
{
  "seed_category": "{seed_category}",
  "terms": [
    {
      "name": "string",
      "priority_score": 1-10 integer
    }
  ]
}

EXAMPLES (do not repeat these):
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


def _normalize_source_name(value: str) -> str:
    """Best-effort normalization for source-derived names into base terms."""
    cleaned = (value or "").strip().strip('"').strip()
    cleaned = cleaned.rstrip(",").strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    # Drop obvious preparation suffixes (keep base).
    cleaned = re.sub(
        r"\b(essential\s+oil|co2\s+extract|absolute|hydrosol|distillate|tincture|glycerite|extract|resin|gum|butter|oil)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_/").strip()
    # Title-case-ish: keep internal capitalization if present.
    return cleaned


def _guess_seed_category_from_name(name: str) -> str:
    """Heuristic mapper into SEED_INGREDIENT_CATEGORIES."""
    n = (name or "").strip().lower()
    if not n:
        return "Medicinal Herbs"
    if any(word in n for word in ("starter", "scoby", "kefir", "culture", "yogurt", "kombucha", "sourdough")):
        return "Fermentation Starters"
    if "clay" in n:
        return "Clays"
    if any(word in n for word in ("salt", "epsom")):
        return "Salts"
    if any(word in n for word in ("acid", "vinegar")):
        return "Acids"
    if any(word in n for word in ("sugar",)):
        return "Sugars"
    if any(word in n for word in ("honey", "molasses", "maple", "agave", "syrup")):
        return "Liquid Sweeteners"
    if any(word in n for word in ("mica", "spirulina", "annatto", "charcoal", "oxide", "ultramarine")):
        return "Colorants"
    if "gum" in n or "xanthan" in n or "guar" in n:
        return "Gums"
    if any(word in n for word in ("frankincense", "myrrh", "damar", "copal", "benzoin")):
        return "Resins"
    if any(word in n for word in ("wax", "beeswax", "candelilla", "carnauba")):
        return "Waxes"
    if any(word in n for word in ("root",)):
        return "Roots"
    if any(word in n for word in ("bark",)):
        return "Barks"
    if any(word in n for word in ("flower", "rose", "lavender", "hibiscus", "jasmine")):
        return "Flowers"
    if any(word in n for word in ("cinnamon", "turmeric", "ginger", "clove", "vanilla", "pepper")):
        return "Spices"
    # Default to medicinal herbs as broadest plant bucket.
    return "Medicinal Herbs"


def _ingest_source_terms_to_db() -> int:
    """Extract candidate bases from bundled CSVs and upsert into source_terms."""
    try:
        from . import database_manager
    except Exception:  # pragma: no cover
        return 0

    rows: List[tuple[str, str, str]] = []
    tgsc_path = DATA_SOURCES_DIR / "tgsc_ingredients.csv"
    cosing_path = DATA_SOURCES_DIR / "cosing.csv"

    if tgsc_path.exists():
        with tgsc_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                raw = (row.get("common_name") or "").strip()
                base = _normalize_source_name(raw)
                if not base:
                    continue
                if _looks_like_form_not_base(base):
                    continue
                cat = _guess_seed_category_from_name(base)
                rows.append((base, cat, "tgsc"))

    if cosing_path.exists():
        with cosing_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                raw = (row.get("INCI name") or row.get("INCI Name") or "").strip()
                base = _normalize_source_name(raw)
                if not base:
                    continue
                if _looks_like_form_not_base(base):
                    continue
                cat = _guess_seed_category_from_name(base)
                rows.append((base, cat, "cosing"))

    if not rows:
        return 0
    return database_manager.upsert_source_terms(rows)


def _select_seed_category(letter_index: int) -> str:
    """Pick a deterministic seed category (stable round-robin)."""
    if not SEED_INGREDIENT_CATEGORIES:
        return "Miscellaneous"
    return SEED_INGREDIENT_CATEGORIES[letter_index % len(SEED_INGREDIENT_CATEGORIES)]


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

        # Optional: ingest deterministic source terms into the DB for source-first ratcheting.
        if INGEST_SOURCE_TERMS:
            try:
                inserted = _ingest_source_terms_to_db()
                if inserted:
                    LOGGER.info("Ingested %s source-derived candidate terms into DB.", inserted)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.warning("Source term ingest failed: %s", exc)

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
        seed_category: str,
    ) -> List[Tuple[str, int]]:
        """Request a small candidate pool from the AI and return (term, priority) tuples."""
        payload = self._request_ai_batch(
            count=count,
            start_after=start_after,
            required_initial=required_initial,
            examples=examples,
            seed_category=seed_category,
        )
        if not payload:
            return []
        out: List[Tuple[str, int]] = []
        for record in payload.get("terms", []) or []:
            name = record.get("name")
            if not isinstance(name, str):
                continue
            cleaned = name.strip()
            if not cleaned:
                continue
            priority = self._extract_priority(record.get("priority_score"))
            out.append((cleaned, priority))
        return out

    def _select_next_term(
        self,
        *,
        start_after: str,
        required_initial: str,
        seed_category: str,
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

        # Source-first: if we have a deterministic next candidate from data sources, take it.
        if USE_SOURCE_TERMS:
            try:
                from . import database_manager
                next_source = database_manager.get_next_source_term(seed_category, required_initial, start_after)
                if next_source and not _looks_like_form_not_base(next_source) and next_source not in self.terms:
                    return next_source, SEED_PRIORITY
            except Exception:  # pragma: no cover
                pass

        while selected is None and attempts < MAX_SELECTION_ATTEMPTS:
            attempts += 1
            # Ramp pool size a bit if we're failing to find a viable term.
            candidate_count = min(MAX_CANDIDATE_POOL_SIZE, max(5, pool_size + (attempts - 1) * 10))
            examples = self._compose_examples(24)
            candidates = self._iter_ai_candidates(
                start_after=start_after,
                required_initial=req_fold.upper(),
                count=candidate_count,
                examples=examples,
                seed_category=seed_category,
            )

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
        """Stage 1: Seed NEW base terms into the task queue.

        Default mode is deterministic gap-fill from the normalized (curated) term list.

        Modes:
        - gapfill (default): pick random gaps per letter from the existing queue and insert the
          next missing normalized term that fits that gap. No AI calls.
        - ai (legacy): AI proposes next terms per cursor (kept for backwards compatibility).
        """
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

        # ------------------------------------------------------------------
        # Mode: deterministic gap-fill (preferred).
        # ------------------------------------------------------------------
        if TERM_GENERATOR_MODE != "ai":
            max_tries = max(1, int(GAPFILL_MAX_TRIES_PER_LETTER or 5))
            # Keep going until we insert `count` new terms, or until a full A→Z pass yields nothing.
            while inserted < normalized_count:
                inserted_this_pass = 0
                for initial in letters:
                    tries = 0
                    while tries < max_tries and inserted < normalized_count:
                        tries += 1
                        start_term = database_manager.get_random_term_for_initial(initial)
                        start_after = start_term or ""
                        end_before = (
                            database_manager.get_next_term_for_initial_after(initial, start_after)
                            if start_term
                            else database_manager.get_next_term_for_initial_after(initial, "")
                        )

                        candidate = database_manager.get_next_missing_normalized_term_between(
                            initial=initial,
                            start_after=start_after,
                            end_before=end_before,
                        )
                        if not candidate:
                            continue
                        term = candidate["term"]
                        seed_category = candidate.get("seed_category") or None
                        if _looks_like_form_not_base(term):
                            continue

                        priority = SEED_PRIORITY
                        was_inserted = database_manager.upsert_term(term, priority, seed_category=seed_category)
                        self._register_term(term, priority)
                        if was_inserted:
                            inserted += 1
                            inserted_this_pass += 1
                            LOGGER.info(
                                "Gapfill queued %s/%s: %s [%s] between '%s' and '%s' (tries=%s/%s)",
                                inserted,
                                normalized_count,
                                term,
                                seed_category or "n/a",
                                start_after or "<start>",
                                end_before or "<end>",
                                tries,
                                max_tries,
                            )
                            break  # move to next letter after a successful insert
                    # After max_tries, move to next letter (even if nothing inserted).

                if inserted_this_pass == 0:
                    LOGGER.warning(
                        "Gapfill made no progress in a full A→Z pass; stopping early at %s/%s inserted.",
                        inserted,
                        normalized_count,
                    )
                    break

            return inserted

        # ------------------------------------------------------------------
        # Mode: legacy AI cursoring (kept for backwards compatibility).
        # ------------------------------------------------------------------
        if not self.include_ai:
            LOGGER.warning("OPENAI_API_KEY missing; skipping AI term generation (TERM_GENERATOR_MODE=ai)")
            return 0

        categories = SEED_INGREDIENT_CATEGORIES or ["Miscellaneous"]
        for idx in range(normalized_count):
            if USE_CATEGORY_CURSOR:
                # Iterate by (letter, category) so every letter advances across all categories.
                initial = letters[(idx // len(categories)) % len(letters)]
                seed_category = categories[idx % len(categories)]
                start_after = database_manager.get_last_term_for_initial_and_seed_category(initial, seed_category) or ""
            else:
                initial = letters[idx % len(letters)]
                seed_category = "Miscellaneous"
                start_after = database_manager.get_last_term_for_initial(initial) or ""
            selected = self._select_next_term(
                start_after=start_after,
                required_initial=initial,
                seed_category=seed_category,
                candidate_pool_size=candidate_pool_size,
            )
            if selected is None:
                LOGGER.warning(
                    "Unable to find next term for (%s, %s) after '%s' on iteration %s/%s",
                    initial,
                    seed_category,
                    start_after or "<start>",
                    idx + 1,
                    normalized_count,
                )
                break

            term, priority = selected
            was_inserted = database_manager.upsert_term(term, priority, seed_category=seed_category)
            self._register_term(term, priority)
            if was_inserted:
                inserted += 1
                LOGGER.info(
                    "Queued term %s/%s: %s [%s] (priority=%s)",
                    idx + 1,
                    normalized_count,
                    term,
                    seed_category,
                    priority,
                )

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
        seed_category: str,
        examples: List[str],
    ) -> Dict[str, Any]:
        user_prompt = TERMS_PROMPT.format(
            count=count,
            start_after=start_after.replace("\"", ""),
            required_initial=(required_initial or "").replace("\"", ""),
            seed_category=(seed_category or "").replace("\"", ""),
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
    parser.add_argument("--ingest-seeds", action="store_true", help="If set, scan --seed-root for seed terms (outputs/ is always ignored)")
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

    # Optional seed ingestion (never reads stage-2 outputs/ files).
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