"""Deterministically normalize source CSVs into base *definition* terms.

Outputs:
- data_builder/ingredients/output/normalized_terms.csv
- Upserts normalized term records into compiler_state.db (normalized_terms table)
- Also ingests *source items* into compiler_state.db (source_items table) so item
  strings do not become base terms (e.g., "Beetroot Powder" should not be a base).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:  # pragma: no cover - allow running as a script
    from . import database_manager
    from .taxonomy_constants import INGREDIENT_CATEGORIES_PRIMARY
    from .taxonomy_constants import ORIGINS, REFINEMENT_LEVELS
except ImportError:  # pragma: no cover
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from data_builder.ingredients import database_manager  # type: ignore
    from data_builder.ingredients.taxonomy_constants import INGREDIENT_CATEGORIES_PRIMARY  # type: ignore
    from data_builder.ingredients.taxonomy_constants import ORIGINS, REFINEMENT_LEVELS  # type: ignore

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_SOURCES_DIR = BASE_DIR / "data_sources"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_CSV = OUTPUT_DIR / "normalized_terms.csv"


_DROP_TOKENS_RE = re.compile(
    r"\b("
    r"essential\s+oil|co2\s+extract|supercritical\s+extract|absolute|hydrosol|distillate|"
    r"tincture|glycerite|alcohol\s+extract|vinegar\s+extract|extract|"
    r"\d+(\.\d+)?\s*%|solution|"
    r"refined|unrefined|deodorized|filtered|unfiltered|unsweetened|sweetened|"
    r")\b",
    flags=re.IGNORECASE,
)

_PUNCT_RE = re.compile(r"[^\w\s\-\&/]", flags=re.UNICODE)
_SPACE_RE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# High-confidence dictionaries for deterministic origin inference
# Keep these conservative to stay under ~5% error.
# ---------------------------------------------------------------------------
ANIMAL_BYPRODUCT_KEYWORDS = {
    "beeswax",
    "lanolin",
    "shellac",
    "gelatin",
    "collagen",
}
ANIMAL_DERIVED_KEYWORDS = {
    "tallow",
    "lard",
    "milk",
    "butter",
    "whey",
    "casein",
    "honey",  # animal-derived (bee product)
}
MARINE_KEYWORDS = {
    "kelp",
    "algae",
    "seaweed",
    "carrageenan",
    "agar",
    "spirulina",
}
MINERAL_KEYWORDS = {
    "oxide",
    "hydroxide",
    "carbonate",
    "chloride",
    "sulfate",
    "phosphate",
    "mica",
    "kaolin",
    "bentonite",
    "clay",
}
FERMENTATION_KEYWORDS = {
    "xanthan",
    "yeast",
    "scoby",
    "kefir",
    "culture",
    "ferment",
}

# High-confidence primary category dictionaries (SOP Ingredient Categories).
# Keep these conservative; prefer false-negative over false-positive.
GRAIN_KEYWORDS = {
    "grain",
    "flour",
    "starch",
    "malt",
    "bran",
    "oat",
    "wheat",
    "rice",
    "corn",
    "maize",
    "barley",
    "rye",
    "sorghum",
    "millet",
    "buckwheat",
    "quinoa",
    "amaranth",
    "tapioca",
    "cassava",
}
NUT_KEYWORDS = {
    "almond",
    "cashew",
    "hazelnut",
    "macadamia",
    "pecan",
    "pistachio",
    "walnut",
    "brazil nut",
    "pine nut",
}
SEED_KEYWORDS = {
    "chia",
    "flax",
    "linseed",
    "sesame",
    "sunflower",
    "pumpkin seed",
    "poppy",
    "hemp",
    "mustard seed",
}
SPICE_KEYWORDS = {
    "cinnamon",
    "clove",
    "nutmeg",
    "mace",
    "vanilla",
    "pepper",
    "paprika",
    "turmeric",
    "ginger",
    "cardamom",
    "cumin",
    "coriander",
    "fennel",
    "anise",
    "allspice",
    "saffron",
}
FLOWER_KEYWORDS = {"rose", "lavender", "hibiscus", "jasmine", "ylang", "neroli"}
FRUIT_KEYWORDS = {
    "apple",
    "lemon",
    "orange",
    "lime",
    "grapefruit",
    "berry",
    "strawberry",
    "raspberry",
    "blueberry",
    "elderberry",
    "acerola",
    "rosehip",
    "mango",
    "banana",
    "pineapple",
    "coconut",
}
VEGETABLE_KEYWORDS = {"cucumber", "carrot", "beet", "beetroot", "pumpkin", "tomato", "potato", "onion", "garlic"}
ACID_KEYWORDS = {"acid", "vinegar", "ascorbic", "citric", "lactic", "acetic", "malic", "tartaric"}
SALT_KEYWORDS = {"salt", "chloride", "sulfate", "sulphate", "phosphate", "carbonate", "bicarbonate"}
CLAY_KEYWORDS = {"kaolin", "bentonite", "montmorillonite", "rhassoul", "ghassoul", "illite"}
MINERAL_KEYWORDS_STRONG = {
    "zinc",
    "magnesium",
    "calcium",
    "sodium",
    "potassium",
    "iron",
    "copper",
    "manganese",
    "silica",
    "oxide",
    "hydroxide",
    "mica",
    "ultramarine",
}
SUGAR_KEYWORDS = {"sugar", "dextrose", "glucose", "fructose", "sucrose"}
LIQUID_SWEETENER_KEYWORDS = {"honey", "molasses", "maple", "agave", "syrup"}

# Very high-confidence synthetic markers (avoid aggressive classification).
SYNTHETIC_MARKERS = {
    "peg-",
    "ppg-",
    "pvp",
    "polyquaternium",
    "acrylates",
    "copolymer",
    "dimethicone",
    "siloxane",
    "quaternium-",
    "isodeceth",
    "ceteareth",
    "laureth",
    "pareth",
    "polysorbate",
}


def guess_origin(term: str, botanical_name: str, sources: list[dict]) -> str:
    t = (term or "").strip().lower()
    # Synthetic markers
    raw_blob = " ".join([(s.get("raw_name") or "") + " " + (s.get("description") or "") for s in sources]).lower()
    if any(m in t for m in SYNTHETIC_MARKERS) or any(m in raw_blob for m in SYNTHETIC_MARKERS):
        return "Synthetic"

    if any(k in t for k in MINERAL_KEYWORDS):
        return "Mineral/Earth"
    if any(k in t for k in FERMENTATION_KEYWORDS):
        return "Fermentation"
    # Marine indicators (term + raw text)
    if any(k in t for k in MARINE_KEYWORDS) or any(k in raw_blob for k in MARINE_KEYWORDS) or "alga" in raw_blob:
        return "Marine-Derived"
    if any(k in t for k in ANIMAL_BYPRODUCT_KEYWORDS):
        return "Animal-Byproduct"
    if any(k in t for k in ANIMAL_DERIVED_KEYWORDS):
        return "Animal-Derived"
    if botanical_name:
        return "Plant-Derived"
    # Conservative default: plant-derived for most maker bases.
    return "Plant-Derived"


def guess_refinement(*, term: str, inci_name: str, origin: str, sources: list[dict]) -> str:
    t = (term or "").strip().lower()
    inci = (inci_name or "").strip().lower()
    raw_names = " ".join([(s.get("raw_name") or "") for s in sources]).lower()
    tgsc_cats = " ".join([(s.get("category") or "") for s in sources]).lower()

    # Fermented
    if any(k in t for k in FERMENTATION_KEYWORDS) or "ferment" in raw_names:
        return "Fermented"

    # Synthesized: if we already believe it's synthetic, treat refinement as Synthesized.
    # This is intentionally early so we don't label synthetic items as "Other".
    if origin == "Synthetic":
        return "Synthesized"
    # Also treat strong synthetic markers in INCI/raw text as synthesized.
    synthetic_blob = " ".join([t, inci, raw_names])
    if any(m in synthetic_blob for m in SYNTHETIC_MARKERS) or any(
        k in synthetic_blob
        for k in (
            "quaternium",
            "edta",
            "polyurethane",
            "polyester",
            "siloxane",
            "dimethicon",
            "acrylate",
            "copolymer",
            "paraben",
            "phenoxyethanol",
            "octinoxate",
            "methoxycinnamate",
            "laureth",
            "pareth",
            "ceteareth",
        )
    ):
        return "Synthesized"

    # Extracted/Distilled signals (from source category or raw name)
    if any(k in raw_names for k in ("essential oil", "co2", "absolute", "concrete", "hydrosol", "tincture", "extract")):
        return "Extracted/Distilled"
    if any(k in tgsc_cats for k in ("essential_oils", "absolutes", "extracts", "concretes")):
        return "Extracted/Distilled"

    # Milled/Ground signals
    if any(k in t for k in ("flour", "starch")) or any(k in raw_names for k in ("flour", "starch")):
        return "Milled/Ground"
    if any(k in raw_names for k in ("powder", "ground", "milled", "micronized")):
        return "Milled/Ground"

    # Extracted fat (butters)
    if "butter" in t or "butter" in raw_names:
        return "Extracted Fat"

    # Oils are often extracted fats; treat as Extracted Fat for makers.
    if " oil" in f" {t} " or " oil" in f" {raw_names} ":
        return "Extracted Fat"

    # Plant parts that are typically minimally processed (dried/cut) when sold as raw materials.
    if any(k in raw_names for k in ("leaf", "bark", "root", "flower", "buds", "seed", "needle", "stem", "herb")):
        if any(k in raw_names for k in ("dried", "dehydrated", "chopped", "crushed", "sliced", "diced", "flakes", "shreds", "ribbons")):
            return "Minimally Processed"
        # If we have a clear plant part but no explicit processing token, still treat as minimally processed
        # (most catalog forms are harvested + dried/handled).
        return "Minimally Processed"

    # Minerals/clays/salts: generally mined + cleaned; map to Raw/Unprocessed for refinement taxonomy.
    if origin == "Mineral/Earth" or any(k in t for k in MINERAL_KEYWORDS):
        return "Raw/Unprocessed"

    return "Other"


# Conservative derived-from dictionary (high-confidence only).
DERIVED_FROM_MAP = {
    "Wheat Flour": "Wheat",
    "Rice Flour": "Rice",
    "Oat Flour": "Oat",
    "Corn Starch": "Corn",
    "Potato Starch": "Potato",
    "Tapioca Starch": "Cassava",
}


def guess_derived_from(term: str) -> str:
    return DERIVED_FROM_MAP.get(term, "")


def guess_primary_category(term: str, inci_name: str, description: str, sources: list[dict]) -> str:
    """Deterministic primary ingredient category (16) using conservative signals."""
    t = (term or "").lower()
    inci = (inci_name or "").lower()
    desc = (description or "").lower()
    raw = " ".join([(s.get("raw_name") or "") for s in sources]).lower()
    blob = " ".join([t, inci, desc, raw])

    # Clays
    if any(k in blob for k in CLAY_KEYWORDS) or "clay" in blob:
        return "Clays"

    # Salts vs Minerals: if explicitly salt/epsom -> Salts, else minerals.
    if "epsom" in blob or " salt" in blob or blob.endswith(" salt"):
        return "Salts"
    if any(k in blob for k in SALT_KEYWORDS) and any(k in blob for k in MINERAL_KEYWORDS_STRONG):
        # inorganic salts are more "Salts" for makers
        return "Salts"
    if any(k in blob for k in MINERAL_KEYWORDS_STRONG):
        return "Minerals"

    # Acids
    if any(k in blob for k in ACID_KEYWORDS):
        return "Acids"

    # Sweeteners/sugars
    if any(k in blob for k in LIQUID_SWEETENER_KEYWORDS):
        return "Liquid Sweeteners"
    if any(k in blob for k in SUGAR_KEYWORDS):
        return "Sugars"

    # Grains/starches
    if any(k in blob for k in GRAIN_KEYWORDS):
        return "Grains"

    # Nuts/seeds
    if any(k in blob for k in NUT_KEYWORDS):
        return "Nuts"
    if any(k in blob for k in SEED_KEYWORDS):
        return "Seeds"

    # Spices
    if any(k in blob for k in SPICE_KEYWORDS):
        return "Spices"

    # Fruits/vegetables
    if any(k in blob for k in FRUIT_KEYWORDS):
        return "Fruits & Berries"
    if any(k in blob for k in VEGETABLE_KEYWORDS):
        return "Vegetables"

    # Flowers
    if any(k in blob for k in FLOWER_KEYWORDS) or " flower" in blob:
        return "Flowers"

    # Roots/barks
    if " root" in blob or blob.endswith("root"):
        return "Roots"
    if " bark" in blob or blob.endswith("bark"):
        return "Barks"

    # No high-confidence category match.
    # Leave blank instead of defaulting (Herbs is not a safe fallback for a high-level sort key).
    return ""


# ---------------------------------------------------------------------------
# Override dictionary (highest-confidence assignments)
# ---------------------------------------------------------------------------
OVERRIDE_EXACT: dict[str, dict[str, str]] = {
    # clays
    "kaolin": {"ingredient_category": "Clays", "origin": "Mineral/Earth", "refinement_level": "Other"},
    "bentonite": {"ingredient_category": "Clays", "origin": "Mineral/Earth", "refinement_level": "Other"},
    # animal/byproduct staples
    "beeswax": {"origin": "Animal-Byproduct", "refinement_level": "Extracted Fat"},
    "lanolin": {"origin": "Animal-Byproduct", "refinement_level": "Extracted Fat"},
    # acids
    "citric acid": {"ingredient_category": "Acids", "origin": "Plant-Derived", "refinement_level": "Other"},
    "lactic acid": {"ingredient_category": "Acids", "origin": "Fermentation", "refinement_level": "Fermented"},
    # salts/minerals staples
    "sodium bicarbonate": {"ingredient_category": "Salts", "origin": "Mineral/Earth", "refinement_level": "Other"},
    "magnesium hydroxide": {"ingredient_category": "Minerals", "origin": "Mineral/Earth", "refinement_level": "Other"},
}


def _confidence_from_signals(*, is_override: bool, score: int) -> int:
    if is_override:
        return 100
    return max(0, min(100, int(score)))


def normalize_base_name(raw: str) -> str:
    """Convert a messy source name into a canonical base term (best-effort)."""
    if not raw:
        return ""
    value = str(raw).strip().strip('"').strip()
    value = value.rstrip(",").strip()
    if not value:
        return ""

    # Remove stray HTML-ish/JS noise.
    value = value.replace("\u00a0", " ")
    value = _PUNCT_RE.sub(" ", value)
    value = _SPACE_RE.sub(" ", value).strip()

    # Remove known non-base tokens.
    value = _DROP_TOKENS_RE.sub("", value)
    value = _SPACE_RE.sub(" ", value).strip(" -/").strip()

    # Collapse obvious INCI blends and polymers to avoid nonsense bases.
    if "/" in value and len(value.split("/")) >= 3:
        return ""
    if any(token in value.upper() for token in ("COPOLYMER", "ACRYLATES", "POLYMER")):
        return ""

    # Title-case while preserving acronyms.
    parts = []
    for part in value.split(" "):
        if part.isupper() and len(part) <= 5:
            parts.append(part)
        else:
            parts.append(part[:1].upper() + part[1:].lower() if part else "")
    return " ".join([p for p in parts if p]).strip()


def guess_seed_category(term: str) -> str:
    """Heuristic mapping into SOP primary Ingredient Categories (16)."""
    n = (term or "").strip().lower()
    if not n:
        return "Herbs"
    if any(w in n for w in ("starter", "scoby", "kefir", "culture", "yogurt", "kombucha", "sourdough")):
        # Primary category doesn't include Fermentation Starters; default to Herbs for now.
        return "Herbs"
    if "clay" in n:
        return "Clays"
    if any(w in n for w in ("salt", "epsom")):
        return "Salts"
    if any(w in n for w in ("acid", "vinegar")):
        return "Acids"
    if "sugar" in n:
        return "Sugars"
    if any(w in n for w in ("honey", "molasses", "maple", "agave", "syrup")):
        return "Liquid Sweeteners"
    if any(w in n for w in ("oxide", "mica", "ultramarine")):
        return "Minerals"
    if "root" in n:
        return "Roots"
    if "bark" in n:
        return "Barks"
    if any(w in n for w in ("rose", "lavender", "hibiscus", "jasmine")):
        return "Flowers"
    if any(w in n for w in ("cinnamon", "turmeric", "ginger", "clove", "vanilla", "pepper")):
        return "Spices"
    # Default to Herbs as the broadest plant bucket.
    return "Herbs"


def _load_tgsc(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def _load_cosing(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def normalize_sources(tgsc_path: Path, cosing_path: Path) -> List[Dict[str, Any]]:
    """Aggregate source rows into normalized base-term records."""
    merged: Dict[str, Dict[str, Any]] = {}

    for row in _load_tgsc(tgsc_path):
        base = normalize_base_name(row.get("common_name") or "")
        if not base:
            continue
        rec = merged.setdefault(
            base,
            {
                "term": base,
                "seed_category": guess_seed_category(base),
                "botanical_name": "",
                "inci_name": "",
                "cas_number": "",
                "description": "",
                "sources": [],
            },
        )
        if not rec["botanical_name"]:
            rec["botanical_name"] = (row.get("botanical_name") or "").strip()
        if not rec["cas_number"]:
            rec["cas_number"] = (row.get("cas_number") or "").strip()
        if not rec["description"]:
            rec["description"] = (row.get("description") or "").strip()
        rec["sources"].append(
            {
                "source": "tgsc",
                "raw_name": (row.get("common_name") or "").strip(),
                "category": (row.get("category") or "").strip(),
                "url": (row.get("url") or "").strip(),
                "synonyms": (row.get("synonyms") or "").strip(),
            }
        )

    for row in _load_cosing(cosing_path):
        raw_inci = (row.get("INCI name") or row.get("INCI Name") or "").strip()
        base = normalize_base_name(raw_inci)
        if not base:
            continue
        rec = merged.setdefault(
            base,
            {
                "term": base,
                "seed_category": guess_seed_category(base),
                "botanical_name": "",
                "inci_name": "",
                "cas_number": "",
                "description": "",
                "sources": [],
            },
        )
        if not rec["inci_name"]:
            rec["inci_name"] = raw_inci
        cas = (row.get("CAS No") or "").strip()
        if cas and not rec["cas_number"]:
            rec["cas_number"] = cas
        if not rec["description"]:
            rec["description"] = (row.get("Chem/IUPAC Name / Description") or "").strip()
        rec["sources"].append(
            {
                "source": "cosing",
                "raw_name": raw_inci,
                "cas_number": cas,
                "function": (row.get("Function") or "").strip(),
                "description": (row.get("Chem/IUPAC Name / Description") or "").strip(),
            }
        )

    out: List[Dict[str, Any]] = []
    for term in sorted(merged.keys(), key=lambda s: (s.casefold(), s)):
        rec = merged[term]
        ingredient_category = guess_primary_category(
            term=term,
            inci_name=rec.get("inci_name", ""),
            description=rec.get("description", ""),
            sources=rec.get("sources", []),
        )
        botanical = rec["botanical_name"]
        origin = guess_origin(term, botanical, rec["sources"])
        refinement = guess_refinement(term=term, inci_name=rec.get("inci_name", ""), origin=origin, sources=rec["sources"])
        derived_from = guess_derived_from(term)

        override = OVERRIDE_EXACT.get(term.strip().lower())
        if override:
            ingredient_category = override.get("ingredient_category", ingredient_category)
            origin = override.get("origin", origin)
            refinement = override.get("refinement_level", refinement)

        # Confidence (coarse, deterministic)
        # If ingredient_category is blank, don't pretend confidence; also don't let it cap overall_confidence.
        cat_conf = 100 if override and "ingredient_category" in override else (85 if ingredient_category else 0)
        origin_conf = 100 if override and "origin" in override else (
            95 if origin in {"Mineral/Earth", "Synthetic", "Fermentation"} else 70
        )
        ref_conf = 100 if override and "refinement_level" in override else (
            90
            if refinement
            in {"Extracted/Distilled", "Extracted Fat", "Fermented", "Milled/Ground", "Synthesized"}
            else (70 if refinement in {"Raw/Unprocessed", "Minimally Processed"} else 55)
        )
        derived_conf = 100 if derived_from else 0
        # overall_confidence should reflect the weakest *known* field.
        # Do not cap overall_confidence with unknown (0) values.
        parts = [c for c in (cat_conf, origin_conf, ref_conf) if c > 0]
        if derived_conf > 0:
            parts.append(derived_conf)
        overall_conf = int(min(parts) if parts else 0)

        sources_json = json.dumps({"sources": rec["sources"]}, ensure_ascii=False, sort_keys=True)
        out.append(
            {
                "term": rec["term"],
                # seed_category is an internal cursor bucket used for iteration.
                # Prefer the ingredient_category if present, otherwise fall back to a heuristic seed bucket.
                "seed_category": ingredient_category or guess_seed_category(term),
                "botanical_name": rec["botanical_name"],
                "inci_name": rec["inci_name"],
                "cas_number": rec["cas_number"],
                "description": rec["description"],
                "ingredient_category": ingredient_category,
                "origin": origin,
                "refinement_level": refinement,
                "derived_from": derived_from,
                "ingredient_category_confidence": cat_conf,
                "origin_confidence": origin_conf,
                "refinement_confidence": ref_conf,
                "derived_from_confidence": derived_conf,
                "overall_confidence": overall_conf,
                "sources_json": sources_json,
                "source_count": len(rec["sources"]),
            }
        )
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "term",
        "seed_category",
        "ingredient_category",
        "origin",
        "refinement_level",
        "derived_from",
        "ingredient_category_confidence",
        "origin_confidence",
        "refinement_confidence",
        "derived_from_confidence",
        "overall_confidence",
        "botanical_name",
        "inci_name",
        "cas_number",
        "description",
        "source_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") or "" for k in fieldnames})


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Normalize ingredient source CSVs into base terms")
    parser.add_argument("--tgsc", default=str(DATA_SOURCES_DIR / "tgsc_ingredients.csv"))
    parser.add_argument("--cosing", default=str(DATA_SOURCES_DIR / "cosing.csv"))
    parser.add_argument("--out", default=str(OUTPUT_CSV))
    parser.add_argument("--no-db", action="store_true", help="Do not upsert into compiler_state.db")
    args = parser.parse_args(argv)

    tgsc_path = Path(args.tgsc).resolve()
    cosing_path = Path(args.cosing).resolve()
    out_path = Path(args.out).resolve()

    # New preferred path: item-first ingestion (writes source_items + normalized_terms).
    try:
        from .ingest_source_items import ingest_sources
    except Exception:  # pragma: no cover
        ingest_sources = None  # type: ignore

    if ingest_sources is not None and not args.no_db:
        inserted_items, inserted_terms = ingest_sources(
            cosing_path=cosing_path,
            tgsc_path=tgsc_path,
            limit=None,
        )
        LOGGER.info("Ingested source_items (new=%s) and normalized_terms (new=%s)", inserted_items, inserted_terms)
        # Export normalized_terms from DB for easy inspection.
        with database_manager.get_session() as session:
            db_rows = session.query(database_manager.NormalizedTerm).order_by(database_manager.NormalizedTerm.term.asc()).all()
        export_rows: List[Dict[str, Any]] = []
        for r in db_rows:
            export_rows.append(
                {
                    "term": r.term,
                    "seed_category": r.seed_category or "",
                    "ingredient_category": r.ingredient_category or "",
                    "origin": r.origin or "",
                    "refinement_level": r.refinement_level or "",
                    "derived_from": r.derived_from or "",
                    "ingredient_category_confidence": r.ingredient_category_confidence or "",
                    "origin_confidence": r.origin_confidence or "",
                    "refinement_confidence": r.refinement_confidence or "",
                    "derived_from_confidence": r.derived_from_confidence or "",
                    "overall_confidence": r.overall_confidence or "",
                    "botanical_name": r.botanical_name or "",
                    "inci_name": r.inci_name or "",
                    "cas_number": r.cas_number or "",
                    "description": r.description or "",
                    "source_count": "",
                }
            )
        write_csv(out_path, export_rows)
        LOGGER.info("Wrote %s normalized terms to %s (from DB)", len(export_rows), out_path)
    else:
        # Legacy fallback: normalize_sources() returns normalized_terms rows only.
        rows = normalize_sources(tgsc_path, cosing_path)
        write_csv(out_path, rows)
        LOGGER.info("Wrote %s normalized terms to %s", len(rows), out_path)

        if not args.no_db:
            inserted = database_manager.upsert_normalized_terms(rows)
            LOGGER.info("Upserted normalized_terms into DB (new=%s)", inserted)


if __name__ == "__main__":
    main()

