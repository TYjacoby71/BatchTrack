"""Deterministic parsing helpers for item-first ingestion (INCI/TGSC).

Goal:
- Treat source CSV rows as *items*.
- Derive a canonical *definition term* (base) used by the compiler queue.
- Extract lightweight lineage hints (origin, ingredient_category, refinement) without AI.

This module is intentionally conservative: prefer "unknown/other" over wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .taxonomy_constants import (
    INGREDIENT_CATEGORIES_PRIMARY,
    ORIGINS,
)


_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s\-\&/()]", flags=re.UNICODE)

# Rough Latin binomial detector (Genus species).
# Must tolerate ALL CAPS INCI rows (e.g., "LAVANDULA ANGUSTIFOLIA ...").
_BINOMIAL_RE = re.compile(r"^\s*([A-Za-z]{2,})\s+([A-Za-z]{2,})\b")
_PAREN_COMMON_RE = re.compile(r"\(([^)]+)\)")

# Common plant-part tokens seen in INCI/TGSC
_PLANT_PART_TOKENS = {
    "leaf",
    "needle",
    "cone",
    "seed",
    "kernel",
    "nut",
    "fruit",
    "berry",
    "flower",
    "root",
    "bark",
    "wood",
    "peel",
    "rind",
    "stem",
    "bud",
}

# Form/process tokens that are *usually* item-level (not definition-level)
_FORM_TOKENS_DROP = {
    "powder",
    "granules",
    "flakes",
    "crystals",
    "chips",
    "shreds",
    "ribbons",
    "wax",
    "oil",
    "butter",
    "extract",
    "tincture",
    "glycerite",
    "hydrosol",
    "absolute",
    "concrete",
    "resin",
    "gum",
    "solution",
    "distillate",
}

# Exceptions: tokens that are definition-level for maker UX (by your direction).
_KEEP_FORM_TOKENS = {"flour"}

# Grain keywords used to decide when to keep "flour" as definition.
_GRAIN_KEYWORDS = {
    "wheat",
    "oat",
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
}

# Synthetic markers (very high confidence)
_SYNTHETIC_MARKERS = {
    "peg-",
    "ppg-",
    "poly",
    "copolymer",
    "acrylate",
    "quaternium",
    "dimethicone",
    "carbomer",
    "laureth",
    "ceteareth",
    "pareth",
    "edta",
}

_FERMENT_MARKERS = {"ferment", "lysate", "filtrate", "culture"}
_MARINE_MARKERS = {"algae", "seaweed", "kelp", "marine", "aqua maris", "sea salt", "chondrus"}
_MINERAL_MARKERS = {"oxide", "dioxide", "hydroxide", "carbonate", "chloride", "sulfate", "phosphate", "mica", "kaolin", "bentonite", "clay"}
_ANIMAL_MARKERS = {"lanolin", "beeswax", "collagen", "keratin", "gelatin", "milk", "whey", "casein", "honey", "tallow", "lard"}


def _clean(value: str) -> str:
    text = (value or "").strip().strip('"').strip()
    text = text.rstrip(",").strip()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def _looks_chemical_like(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # digits + hyphens/slashes tends to be INCI chemistry
    if any(ch.isdigit() for ch in t) and any(sym in t for sym in ("-", "/", ",")):
        return True
    return False


def _title_case_soft(text: str) -> str:
    """Title-case while preserving common acronyms and hyphenated tokens."""
    if not text:
        return ""
    parts = []
    for tok in text.split(" "):
        if not tok:
            continue
        if tok.upper() in {"CO2", "PEG", "PPG"} or re.match(r"^[A-Z0-9\-]+$", tok):
            parts.append(tok.upper())
        else:
            parts.append(tok[:1].upper() + tok[1:].lower())
    return " ".join(parts).strip()


def derive_definition_term(raw_name: str) -> str:
    """Derive a canonical definition term from an item string.

    Examples:
    - "Beetroot Powder" -> "Beetroot"
    - "ABIES ALBA CONE OIL" -> "Abies Alba"
    - "Triticum Vulgare Kernel Flour" -> "Triticum Vulgare Kernel Flour" (keep flour)
    """
    cleaned = _clean(raw_name)
    if not cleaned:
        return ""

    # If it's clearly chemical, keep as-is (normalized spacing).
    if _looks_chemical_like(cleaned):
        return cleaned

    lowered = cleaned.lower()

    # If we have a Latin binomial at the start, prefer a common name in parentheses when present.
    m = _BINOMIAL_RE.match(cleaned)
    if m:
        genus_raw = m.group(1)
        species_raw = m.group(2)
        genus = genus_raw[:1].upper() + genus_raw[1:].lower() if genus_raw else ""
        species = (species_raw or "").lower()
        common_match = _PAREN_COMMON_RE.search(cleaned)
        if common_match:
            common_raw = _clean(common_match.group(1))
            common = _title_case_soft(common_raw)
            if common:
                # Special-case: "Beet" + root -> Beetroot (common maker term)
                if common.strip().lower() == "beet" and "root" in lowered:
                    return "Beetroot"
                # Grain flour definitions: (Wheat) kernel flour -> Wheat Flour
                if "flour" in lowered and any(k in lowered for k in _GRAIN_KEYWORDS):
                    return _title_case_soft(f"{common} Flour")
                # Default: use common name as definition (more maker-friendly than Latin).
                return common
        # Otherwise: use Genus species as canonical base.
        return f"{genus} {species}".strip()

    # Keep flour as definition for grain-like items.
    if "flour" in lowered and any(k in lowered for k in _GRAIN_KEYWORDS):
        return _title_case_soft(cleaned)

    # Drop trailing form tokens (powder/oil/extract/etc) when present.
    tokens = lowered.split(" ")
    while tokens:
        last = tokens[-1]
        if last in _KEEP_FORM_TOKENS:
            break
        if last in _FORM_TOKENS_DROP:
            tokens.pop()
            continue
        break
    # If we just stripped a form (e.g., "... seed oil" -> "... seed"), drop trailing plant-part token too.
    if tokens and tokens[-1] in _PLANT_PART_TOKENS:
        tokens.pop()
    base = " ".join(tokens).strip()
    if not base:
        base = lowered
    return _title_case_soft(base)


def infer_origin(raw_name: str) -> str:
    """Best-effort single-select origin."""
    cleaned = _clean(raw_name)
    t = cleaned.lower()

    if any(k in t for k in _MARINE_MARKERS):
        return "Marine-Derived"
    if any(k in t for k in _FERMENT_MARKERS):
        return "Fermentation"
    if any(k in t for k in _MINERAL_MARKERS):
        return "Mineral/Earth"
    if any(k in t for k in _ANIMAL_MARKERS):
        # keep split between animal-derived and byproduct later; for now treat as Animal-Derived
        return "Animal-Derived"
    if any(k in t for k in _SYNTHETIC_MARKERS) or _looks_chemical_like(t):
        return "Synthetic"

    # Botanical signals: Latin-ish binomial or plant parts
    if _BINOMIAL_RE.match(cleaned) or any(p in t for p in _PLANT_PART_TOKENS):
        return "Plant-Derived"

    # Conservative default: Plant-Derived (matches historic behavior).
    return "Plant-Derived"


def infer_primary_category(definition_term: str, origin: str, raw_name: str = "") -> str:
    """Best-effort ingredient category under an origin (single-select).

    `raw_name` is optional context from the source item string (useful for cases
    where the definition term is intentionally shorter, e.g., "Jojoba" derived
    from "Jojoba Seed Oil").
    """
    t = (definition_term or "").lower()
    raw = (raw_name or "").lower()
    blob = f"{t} {raw}".strip()
    o = (origin or "").strip()

    if o == "Synthetic":
        if any(k in t for k in ("copolymer", "polymer", "acrylate", "carbomer", "poly")):
            return "Synthetic - Polymers"
        if any(k in t for k in ("laureth", "ceteareth", "sulfate", "sulfonate", "betaine", "glucoside", "surfactant")):
            return "Synthetic - Surfactants"
        if any(k in t for k in ("glycol", "alcohol", "solvent", "propanediol", "butylene", "propylene")):
            return "Synthetic - Solvents"
        if any(k in t for k in ("paraben", "phenoxyethanol", "preservative", "benzoate", "sorbate")):
            return "Synthetic - Preservatives"
        if any(k in t for k in ("ci ", "colour", "color", "dye", "lake", "pigment", "oxide", "ultramarine")):
            return "Synthetic - Colorants"
        if any(k in t for k in ("hydroxide", "carbonate", "bicarbonate", "chloride", "phosphate")):
            return "Synthetic - Salts & Bases"
        return "Synthetic - Other"

    if o == "Fermentation":
        if "acid" in t:
            return "Fermentation - Acids"
        if any(k in t for k in ("gum", "xanthan", "dextran", "pullulan")):
            return "Fermentation - Polysaccharides"
        return "Fermentation - Other"

    if o == "Marine-Derived":
        if any(k in t for k in ("salt", "mineral")):
            return "Marine - Minerals"
        return "Marine - Botanicals"

    if o in {"Animal-Derived", "Animal-Byproduct"}:
        if any(k in t for k in ("milk", "whey", "casein", "lactose")):
            return "Animal - Dairy"
        if any(k in t for k in ("tallow", "lard", "fat", "oil")):
            return "Animal - Fats"
        if any(k in t for k in ("collagen", "keratin", "gelatin", "protein", "peptide")):
            return "Animal - Proteins"
        return "Animal - Other"

    # Mineral/Earth
    if o == "Mineral/Earth":
        if "clay" in t or any(k in t for k in ("kaolin", "bentonite")):
            return "Clays"
        if "salt" in t or "chloride" in t:
            return "Salts"
        if "acid" in t:
            return "Acids"
        return "Minerals"

    # Plant-derived (default)
    if any(k in blob for k in ("salt", "chloride")):
        return "Salts"
    if "acid" in blob:
        return "Acids"
    if "sugar" in blob:
        return "Sugars"
    if any(k in blob for k in ("honey", "molasses", "maple", "agave", "syrup")):
        return "Liquid Sweeteners"
    if any(k in blob for k in _GRAIN_KEYWORDS) or any(k in blob for k in ("starch", "flour", "malt", "bran")):
        return "Grains"
    if any(k in blob for k in ("almond", "walnut", "hazelnut", "macadamia", "pecan", "pistachio", "cashew")):
        return "Nuts"
    if any(k in blob for k in ("chia", "sesame", "flax", "linseed", "sunflower", "pumpkin seed", "poppy")):
        return "Seeds"
    # Seed/kernel/nut oils should classify as Seeds/Nuts even when the definition is the plant name.
    if "seed oil" in blob or "kernel oil" in blob:
        return "Seeds"
    if "nut oil" in blob:
        return "Nuts"
    if any(k in t for k in ("cinnamon", "turmeric", "ginger", "clove", "vanilla", "pepper", "cardamom", "cumin")):
        return "Spices"
    if any(k in t for k in ("rose", "lavender", "hibiscus", "jasmine", "neroli")):
        return "Flowers"
    if "root" in t:
        return "Roots"
    if "bark" in t:
        return "Barks"
    if any(k in t for k in ("fruit", "berry", "citrus", "apple", "lemon", "orange")):
        return "Fruits & Berries"
    if any(k in t for k in ("carrot", "beet", "beetroot", "potato", "tomato", "cucumber")):
        return "Vegetables"

    # Conservative fallback
    return "Herbs"


def infer_refinement(definition_term: str, raw_name: str) -> str:
    """Best-effort refinement level for the definition (not item-specific)."""
    blob = f"{definition_term} {raw_name}".lower()
    if any(k in blob for k in ("ferment", "lysate", "filtrate")):
        return "Fermented"
    if any(k in blob for k in ("essential oil", "co2", "absolute", "hydrosol", "distillate", "extract", "tincture", "glycerite")):
        return "Extracted/Distilled"
    if any(k in blob for k in ("flour", "powder", "starch", "milled", "ground")):
        return "Milled/Ground"
    if any(k in blob for k in ("butter", "oil", "fat")):
        return "Extracted Fat"
    if any(k in blob for k in ("copolymer", "poly", "peg-", "ppg-")) or any(ch.isdigit() for ch in blob):
        return "Synthesized"
    return "Minimally Processed"


@dataclass(frozen=True)
class ParsedItem:
    raw_name: str
    definition_term: str
    origin: str
    ingredient_category: str
    refinement_level: str

