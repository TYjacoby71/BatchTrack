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

# Tokens that are common words / chemical descriptors (not botanical genera). If a name starts
# with these, do NOT treat the first two tokens as a botanical binomial.
# This prevents false binomial parsing like:
# - "bitter almond oil (fixed)" -> "Fixed"
# - "ACID RED 18" -> "Acid red" (dropping the number)
# - "HC YELLOW NO. 10" -> "Hc yellow no" (dropping the number)
_NON_BINOMIAL_GENUS = {
    "acid",
    "basic",
    "solvent",
    "pigment",
    "hc",
    "fd",
    "d&c",
    "color",
    "colour",
    "yellow",
    "red",
    "blue",
    "green",
    "orange",
    "violet",
    "black",
    "brown",
    "white",
    "bitter",
    "sweet",
    "fixed",
    "alcohol",
}
_PAREN_COMMON_RE = re.compile(r"\(([^)]+)\)")
_BINOMIAL_STOPWORDS = {
    "oil",
    "extract",
    "butter",
    "wax",
    "resin",
    "gum",
    "water",
    "powder",
    "flour",
    "starch",
    "juice",
    "concrete",
    "absolute",
}

# Tokens that should NOT be treated as a botanical epithet (they indicate part/form).
def _format_botanical_name(tokens: list[str]) -> str:
    """Format botanical tokens as 'Genus species [epithet]' with lowercase epithets."""
    toks = [t for t in tokens if t]
    if not toks:
        return ""
    genus = toks[0][:1].upper() + toks[0][1:].lower()
    rest = [t.lower() for t in toks[1:]]
    # Deduplicate accidental repeats (e.g., 'angustifolia angustifolia')
    out = [genus]
    for t in rest:
        if out and out[-1].lower() == t.lower():
            continue
        out.append(t)
    return " ".join(out).strip()

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

# Tokens that should NOT be treated as a botanical epithet (they indicate part/form).
_BOTANICAL_NON_EPITHET_TOKENS = set(_PLANT_PART_TOKENS) | set(_FORM_TOKENS_DROP) | _BINOMIAL_STOPWORDS | {
    "sp",
    "ssp",
    "subsp",
    "var",
    "cv",
    "hybrid",
    "x",
    # non-taxonomic processing/biotech tokens that often appear as the 3rd token in INCI names
    # (avoid incorrectly treating these as botanical epithets)
    "callus",
    "culture",
    "cell",
    "cells",
    "meristem",
    "tissue",
    "filtrate",
    "lysate",
    "ferment",
    "fermented",
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
    "oleth",
    "steareth",
    "ceteth",
    "glycereth",
    "pareth",
    "edta",
}

_FERMENT_MARKERS = {"ferment", "lysate", "filtrate", "culture", "conditioned media", "exosome"}
_MARINE_MARKERS = {"algae", "seaweed", "kelp", "marine", "aqua maris", "sea salt", "chondrus", "carrageenan", "agar", "alginate"}
_MINERAL_MARKERS = {
    # True mineral/material signals (avoid generic salt anions; those are ambiguous in organic salts).
    "clay",
    "kaolin",
    "bentonite",
    "mica",
    "talc",
    "silica",
    "oxide",
    "dioxide",
    "mineral",
    "salt",
}
_ANIMAL_MARKERS = {
    "lanolin",
    "beeswax",
    "cera alba",
    "cera flava",
    "collagen",
    "keratin",
    "gelatin",
    "milk",
    "whey",
    "casein",
    "honey",
    "tallow",
    "lard",
    "silk",
    "wool",
    "cashmere",
    "angora",
}

# Word-boundary fiber markers (avoid false positives like "longum" containing "gum").
_FIBER_MARKER_RE = re.compile(
    r"\b(gum|cellulose|fiber|fibre|pectin|inulin|mucilage|lignin|beta[\s\-]?glucan)\b"
)


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


# Plant-part tokens that should be preserved at the item level for botanicals.
_PLANT_PART_LABELS: dict[str, str] = {
    "bark": "Bark",
    "leaf": "Leaf",
    "seed": "Seed",
    "flower": "Flower",
    "root": "Root",
    "bud": "Bud",
    "stem": "Stem",
    "fruit": "Fruit",
    "peel": "Peel",
    "rind": "Rind",
    "kernel": "Kernel",
    "nut": "Nut",
    "wood": "Wood",
    "cone": "Cone",
    "needle": "Needle",
    "herb": "Herb",
    "rhizome": "Rhizome",
    # less common but appears in CosIng
    "seedcoat": "Seedcoat",
    "shell": "Shell",
    "branch": "Branch",
}


def extract_plant_part(raw_name: str) -> str:
    """Best-effort extract a single plant-part label from an item name."""
    cleaned = _clean(raw_name)
    if not cleaned:
        return ""
    t = cleaned.lower()
    # Prefer longer tokens first (seedcoat before seed).
    for tok in sorted(_PLANT_PART_LABELS.keys(), key=lambda s: -len(s)):
        if re.search(rf"\b{re.escape(tok)}\b", t):
            return _PLANT_PART_LABELS[tok]
    return ""

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

    # Special-case: denatured alcohol families are not botanicals.
    # Keep the definition stable and represent the grade/spec at the item level.
    if lowered.startswith("alcohol denat"):
        return "Alcohol Denat"

    # Remove parenthetical fixed-oil marker before further parsing.
    # This prevents "(fixed)" being treated as a "common name" override.
    cleaned = re.sub(r"\(\s*fixed\s*\)", "", cleaned, flags=re.IGNORECASE).strip()
    lowered = cleaned.lower()

    # If we have a Latin binomial at the start, prefer a common name in parentheses when present.
    m = _BINOMIAL_RE.match(cleaned)
    if m:
        genus_raw = m.group(1)
        species_raw = m.group(2)
        genus = genus_raw[:1].upper() + genus_raw[1:].lower() if genus_raw else ""
        species = (species_raw or "").lower()
        # Guardrail: reject common non-botanical leading tokens (dyes, descriptors, etc.)
        # and generic item tokens as "species" (e.g., "Jojoba Oil").
        is_binomial = genus.lower() not in _NON_BINOMIAL_GENUS and species not in _BINOMIAL_STOPWORDS
        if is_binomial:
            common_match = _PAREN_COMMON_RE.search(cleaned)
            if common_match:
                common_raw = _clean(common_match.group(1))
                common = _title_case_soft(common_raw)
                if common:
                    # Never allow "(fixed)" to become the definition term.
                    if common.strip().lower() == "fixed":
                        common = ""
                    if common:
                        # Special-case: "Beet" + root -> Beetroot (common maker term)
                        if common.strip().lower() == "beet" and "root" in lowered:
                            return "Beetroot"
                        # Grain flour definitions: (Wheat) kernel flour -> Wheat Flour
                        if "flour" in lowered and any(k in lowered for k in _GRAIN_KEYWORDS):
                            return _title_case_soft(f"{common} Flour")
                        # Default: use common name as definition (more maker-friendly than Latin).
                        return common
            # Otherwise: include an optional 3rd botanical epithet token when present.
            # This helps distinguish cases like:
            # - Citrus aurantium bergamia (bergamot) vs Citrus aurantium amara (bitter orange)
            tokens = cleaned.split()
            epithet = ""
            if len(tokens) >= 3:
                cand = tokens[2].strip().lower()
                if cand and cand not in _BOTANICAL_NON_EPITHET_TOKENS and cand.isalpha():
                    epithet = cand
            base_tokens = [genus, species] + ([epithet] if epithet else [])
            return _format_botanical_name([t for t in base_tokens if t])

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

    # Dye/colorant families (usually synthetic; avoid falling back to Plant-Derived).
    if re.search(r"\b(hc|fd|d&c)\s+(red|blue|yellow|orange|green|violet|black|brown|white)\b", t) or re.search(
        r"\b(acid|basic|solvent|pigment)\s+(red|blue|yellow|orange|green|violet|black|brown)\b",
        t,
    ):
        return "Synthetic"

    if any(k in t for k in _MARINE_MARKERS):
        return "Marine-Derived"
    if any(k in t for k in _FERMENT_MARKERS):
        return "Fermentation"
    if any(k in t for k in _ANIMAL_MARKERS):
        # keep split between animal-derived and byproduct later; for now treat as Animal-Derived
        return "Animal-Derived"
    # Amine oxides are an INCI surfactant family (synthetic), not mineral oxides.
    if "amine oxide" in t:
        return "Synthetic"
    if any(k in t for k in _SYNTHETIC_MARKERS) or _looks_chemical_like(t):
        return "Synthetic"

    # Inorganic salt heuristic (handles cases like "SODIUM CHLORIDE" even without other mineral tokens).
    parts = t.split()
    inorganic_cations = {"sodium", "potassium", "calcium", "magnesium", "zinc", "iron", "copper", "aluminum", "ammonium"}
    inorganic_anions = {
        "chloride",
        "bromide",
        "iodide",
        "fluoride",
        "sulfate",
        "phosphate",
        "carbonate",
        "bicarbonate",
        "hydroxide",
        "nitrate",
        "silicate",
        "borate",
        "peroxide",
        "dioxide",
        "oxide",
    }
    # Multi-word salts: if it begins with a simple cation and ends with a common inorganic anion,
    # treat as Mineral/Earth; otherwise treat as Synthetic organic salt.
    if len(parts) >= 2 and parts[0] in inorganic_cations and parts[-1] in inorganic_anions:
        return "Mineral/Earth"
    if len(parts) == 2 and parts[1] in inorganic_anions:
        # If the cation is a simple inorganic cation, treat as mineral; otherwise treat as synthetic organic salt.
        return "Mineral/Earth" if parts[0] in inorganic_cations else "Synthetic"
    if len(parts) >= 2 and parts[0] in inorganic_cations and parts[-1].endswith(("ate", "ite", "ide", "urate")):
        return "Synthetic"

    if any(k in t for k in _MINERAL_MARKERS):
        return "Mineral/Earth"

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
        # Dye/colorant families
        if re.search(r"\b(hc|fd|d&c)\b", t) or re.search(r"\b(acid|basic|solvent|pigment)\b", t):
            return "Synthetic - Colorants"
        if any(k in t for k in ("copolymer", "polymer", "acrylate", "carbomer", "poly")):
            return "Synthetic - Polymers"
        if any(
            k in t
            for k in (
                "amine oxide",
                "laureth",
                "ceteareth",
                "oleth",
                "steareth",
                "ceteth",
                "pareth",
                "glycereth",
                "sulfate",
                "sulfonate",
                "betaine",
                "glucoside",
                "sultaine",
                "amphoacetate",
                "isethionate",
                "sarcosinate",
                "taurate",
                "surfactant",
            )
        ):
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
        if any(k in blob for k in ("wool", "silk", "cashmere", "angora")):
            return "Animal - Fibers"
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
    if _FIBER_MARKER_RE.search(blob):
        return "Fibers"
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


def extract_variation_and_physical_form(raw_name: str) -> tuple[str, str]:
    """Extract (variation, physical_form) from a source item string.

    This is intentionally conservative and focuses on high-signal, common patterns
    that appear in CosIng/TGSC rows.

    Examples:
    - "SIMMONDSIA CHINENSIS SEED OIL" -> ("Seed Oil", "Oil")
    - "JOJOBA SEED OIL" -> ("Seed Oil", "Oil")
    - "LAVANDULA ANGUSTIFOLIA HERB OIL" -> ("Herb Oil", "Oil")
    """
    cleaned = _clean(raw_name)
    t = cleaned.lower().strip(" ,")
    if not t:
        return "", ""

    # Normalize repeated whitespace/hyphens already handled by _clean.

    # CO2 / supercritical extracts (must win over oil keywords like "seed oil")
    # Examples:
    # - "punica granatum seed oil CO2 extract" -> ("CO2 Extract", "Liquid")
    # - "rosehip CO2 extract" -> ("CO2 Extract", "Liquid")
    if re.search(r"\bco2\b", t) and ("extract" in t or "supercritical" in t):
        return "CO2 Extract", "Liquid"
    if "supercritical extract" in t:
        return "CO2 Extract", "Liquid"

    # Preserve botanical part for common part+extract patterns (otherwise they collapse into "Extract").
    # Examples:
    # - "AESCULUS HIPPOCASTANUM BARK EXTRACT" -> ("Bark Extract", "Liquid")
    # - "PRUNUS PERSICA LEAF EXTRACT" -> ("Leaf Extract", "Liquid")
    for tok, label in _PLANT_PART_LABELS.items():
        if re.search(rf"\b{re.escape(tok)}\s+(?:cell\s+)?extract\b", t):
            return f"{label} Extract", "Liquid"

    # Preserve part for part+powder patterns (otherwise they collapse into "Powder").
    for tok, label in _PLANT_PART_LABELS.items():
        if re.search(rf"\b{re.escape(tok)}\s+powder\b", t):
            return f"{label} Powder", "Powder"

    # Concentrations / solutions (high-signal, common in catalogs)
    # Examples: "SODIUM HYDROXIDE 50% SOLUTION", "LACTIC ACID 80%"
    if "solution" in t or re.search(r"\b\d{1,3}\s*%(\s*w/w)?\b", t):
        return "Solution", "Liquid"
    # Denatured alcohol families (CosIng: "SD ALCOHOL 40", etc.)
    if "sd alcohol" in t:
        m = re.search(r"\bsd\s+alcohol\s+(\d{1,3})\b", t)
        if m:
            return f"SD Alcohol {m.group(1)}", "Liquid"
        return "SD Alcohol", "Liquid"
    if re.search(r"\balcohol\s+\d{1,3}\b", t) and "denat" in t:
        m = re.search(r"\balcohol\s+(\d{1,3})\b", t)
        if m:
            return f"Alcohol {m.group(1)}", "Liquid"
        return "Alcohol", "Liquid"

    # Food-like forms (important for makers; common in TGSC/other sources)
    if " puree" in f" {t} " or " purée" in f" {t} " or t.endswith(" puree") or t.endswith(" purée"):
        return "Puree", "Liquid"
    if " juice" in f" {t} " or t.endswith(" juice"):
        return "Juice", "Liquid"
    if " pulp" in f" {t} " or t.endswith(" pulp"):
        return "Pulp", "Paste"
    if "oil (fixed)" in t or t.endswith("(fixed)"):
        return "Fixed Oil", "Oil"
    if " vinegar" in f" {t} " or t.endswith(" vinegar"):
        return "Vinegar", "Liquid"
    if " nectar" in f" {t} " or t.endswith(" nectar"):
        return "Nectar", "Liquid"
    # Common misspelling observed in source data
    if " extraxt" in f" {t} " or t.endswith(" extraxt"):
        return "Extract", "Liquid"

    # Oil variants (plant parts)
    for part in ("seed", "kernel", "nut", "leaf", "needle", "cone", "bark", "wood", "flower", "herb", "root", "rhizome", "stem"):
        token = f"{part} oil"
        if token in t:
            return _title_case_soft(token), "Oil"
    # Plain oil (no plant part specified) — common in INCI.
    if t.endswith(" oil"):
        return "Oil", "Oil"
    # TGSC: oils often include extra trailing descriptors (country, processing notes, etc).
    # If "oil" appears as a token and it's not an "oil replacer", classify as Oil.
    if re.search(r"\boil\b", t) and "replacer" not in t and "(fixed)" not in t:
        return "Oil", "Oil"

    # Plant part materials (non-oil) - useful for grouping and term bundling.
    for part in ("seed", "kernel", "nut", "leaf", "needle", "cone", "bark", "wood", "flower", "herb", "root", "rhizome", "stem", "peel", "fruit", "berry", "bran", "germ"):
        if t.endswith(f" {part}"):
            return _title_case_soft(part), "Whole"
    # Common botanical fractions/actives that appear as trailing tokens (CosIng/TGSC)
    if t.endswith(" oleosomes") or " oleosomes" in f" {t} ":
        return "Oleosomes", "Oil"
    if t.endswith(" vesicles") or " vesicles" in f" {t} ":
        return "Vesicles", "Liquid"
    if t.endswith(" oligosaccharides") or " oligosaccharides" in f" {t} ":
        return "Oligosaccharides", "Solid"
    if t.endswith(" catechins") or " catechins" in f" {t} ":
        return "Catechins", "Solid"
    if t.endswith(" prenylflavonoids") or " prenylflavonoids" in f" {t} ":
        return "Prenylflavonoids", "Solid"
    if t.endswith(" terpenoids") or " terpenoids" in f" {t} ":
        return "Terpenoids", "Solid"
    if t.endswith(" fiber") or t.endswith(" fibre"):
        return "Fiber", "Powder"
    if t.endswith(" silicates") or t.endswith(" silicate"):
        return "Silicates", "Solid"

    # Essential oil / absolute / concrete are treated as variation; physical_form still Oil/Liquid.
    if "essential oil" in t:
        return "Essential Oil", "Oil"

    # Polymer / surfactant families (synthetic derivatives)
    if "crosspolymer" in t:
        return "Crosspolymer", "Solid"
    if "copolymer" in t:
        return "Copolymer", "Solid"
    if any(k in t for k in ("peg-", "glycereth", "laureth", "ceteareth", "oleth", "steareth", "ceteth", "pareth", "alketh")):
        return "Ethoxylated", "Liquid"
    # Generic "-eth" family (e.g., MYRETH-3, ISODECETH-2)
    if re.search(r"\b[a-z]{2,}eth-\d+\b", t):
        return "Ethoxylated", "Liquid"
    if "ppg-" in t:
        return "Propoxylated", "Liquid"
    if "poloxamer" in t:
        return "Poloxamer", "Solid"
    if any(k in t for k in ("quaternium", "trimonium", "polyquaternium")):
        return "Quaternary Ammonium", "Solid"
    if any(k in t for k in ("dimethicone", "siloxane", "silicone")):
        return "Silicone", "Liquid"

    # Surfactant / cleanser families (common INCI suffix families)
    # Keep these as variation tags so items can be filtered and grouped deterministically.
    if "amine oxide" in t:
        return "Amine Oxide", "Liquid"
    if re.search(r"\bbetaine\b", t):
        return "Betaine", "Liquid"
    if "hydroxysultaine" in t or "sultaine" in t:
        return "Sultaine", "Liquid"
    if re.search(r"\bglucoside\b", t):
        return "Glucoside", "Liquid"
    if re.search(r"\bisethionate\b", t):
        return "Isethionate", "Solid"
    if re.search(r"\bsarcosinate\b", t):
        return "Sarcosinate", "Liquid"
    if re.search(r"\btaurate\b", t) or t.endswith("taurate"):
        return "Taurate", "Liquid"
    if re.search(r"\blactylate\b", t):
        return "Lactylate", "Solid"
    if "amphoacetate" in t or "amphodiacetate" in t:
        return "Amphoacetate", "Liquid"
    if "glutamate" in t:
        return "Glutamate", "Solid"
    if "glycinate" in t:
        return "Glycinate", "Solid"
    if "alaninate" in t:
        return "Alaninate", "Solid"
    # Many INCI salts are concatenated (e.g., "cumenesulfonate", "lignosulfonate").
    if re.search(r"sulfonate$", t) or re.search(r"\bsulfonate\b", t):
        return "Sulfonate", "Solid"
    if re.search(r"\bsulfosuccinate\b", t):
        return "Sulfosuccinate", "Liquid"
    if re.search(r"\bsulfoacetate\b", t):
        return "Sulfoacetate", "Liquid"

    # Common physical material forms
    if " butter" in f" {t} " or t.endswith(" butter"):
        return "Butter", "Butter"
    if " wax" in f" {t} " or t.endswith(" wax") or " cera" in f" {t} ":
        return "Wax", "Wax"
    if " esters" in f" {t} " or t.endswith(" esters"):
        # Esters are often liquids/waxes; keep as Liquid for now (safe for UI gating).
        return "Esters", "Liquid"
    if t.endswith(" ester"):
        return "Ester", "Liquid"
    if " oleyl esters" in t:
        return "Oleyl Esters", "Liquid"
    if "oleoresin" in t:
        return "Oleoresin", "Resin"
    if " resin" in f" {t} " or t.endswith(" resin"):
        return "Resin", "Resin"
    if " gum" in f" {t} " or t.endswith(" gum"):
        return "Gum", "Gum"
    if " gel" in f" {t} " or t.endswith(" gel"):
        return "Gel", "Gel"
    if " paste" in f" {t} " or t.endswith(" paste"):
        return "Paste", "Paste"

    if "ferment filtrate" in t:
        return "Ferment Filtrate", "Liquid"
    if "ferment lysate" in t or "ferment-lysate" in t:
        return "Ferment Lysate", "Liquid"
    if "ferment" in t and "filtrate" in t:
        return "Ferment Filtrate", "Liquid"
    if "ferment" in t:
        return "Ferment", "Liquid"
    if "lysate" in t:
        return "Lysate", "Liquid"
    if "conditioned media" in t:
        return "Conditioned Media", "Liquid"
    # Plant/biotech culture families (common in CosIng)
    if "meristem cell culture" in t:
        return "Meristem Cell Culture", "Liquid"
    if "meristem cell" in t:
        return "Meristem Cell", "Liquid"
    if "callus culture" in t:
        return "Callus Culture", "Liquid"
    if "callus" in t:
        return "Callus", "Liquid"
    if "cell culture" in t:
        return "Cell Culture", "Liquid"
    if "extracellular vesicles" in t:
        return "Extracellular Vesicles", "Liquid"
    if "exosomes" in t:
        return "Exosomes", "Liquid"
    if "protoplasts" in t:
        return "Protoplasts", "Liquid"

    # Processing modifiers (single-label best-effort)
    if "hydrolyzed" in t:
        return "Hydrolyzed", "Liquid"
    if "hydrogenated" in t:
        return "Hydrogenated", "Solid"
    if "acetylated" in t:
        return "Acetylated", "Liquid"
    if "cold pressed" in t or "cold-pressed" in t:
        return "Cold-Pressed", "Oil"
    if "steam distilled" in t or "steam-distilled" in t:
        return "Steam-Distilled", "Oil"
    if "refined" in t:
        return "Refined", "Liquid"
    if "unrefined" in t:
        return "Unrefined", "Liquid"
    if "virgin" in t:
        return "Virgin", "Oil"
    if "deodorized" in t or "deodorised" in t:
        return "Deodorized", "Oil"
    if "sulfated" in t:
        return "Sulfated", "Solid"
    if "phosphated" in t:
        return "Phosphated", "Solid"

    if "co2 extract" in t or "co₂ extract" in t:
        return "CO2 Extract", "Liquid"
    if "absolute" in t:
        return "Absolute", "Liquid"
    if "concrete" in t:
        return "Concrete", "Solid"
    if " expressed" in f" {t} ":
        # Common label for citrus oils; treat as a variation of oil extraction.
        return "Expressed", "Oil"
    if "hydrosol" in t or " flower water" in t or t.endswith(" water"):
        return "Hydrosol", "Hydrosol"
    if "distillates" in t or "distillate" in t:
        return "Distillate", "Liquid"
    if "infusion" in t:
        return "Infusion", "Liquid"
    if "tincture" in t:
        return "Tincture", "Liquid"
    if "glycerite" in t:
        return "Glycerite", "Liquid"
    if "extract" in t:
        return "Extract", "Liquid"

    # Powders / flours
    if " powder" in f" {t} " or t.endswith(" powder"):
        return "Powder", "Powder"
    if " flour" in f" {t} " or t.endswith(" flour"):
        return "Flour", "Powder"
    if " starch" in f" {t} " or t.endswith(" starch"):
        return "Starch", "Powder"
    if t.endswith(" crystals") or " crystals" in f" {t} ":
        return "Crystals", "Solid"
    if t.endswith(" granules") or " granules" in f" {t} ":
        return "Granules", "Solid"
    if t.endswith(" flakes") or " flakes" in f" {t} ":
        return "Flakes", "Solid"
    if t.endswith(" meal") or " meal" in f" {t} ":
        return "Meal", "Powder"

    # Organic acid salts / esters (very common in INCI)
    # If it ends in a salt-like suffix, treat as Salt; if it ends in a fatty-acid ester suffix, treat as Esters.
    _CATION_PREFIXES = (
        "sodium",
        "potassium",
        "calcium",
        "magnesium",
        "zinc",
        "iron",
        "copper",
        "aluminum",
        "silver",
        "lithium",
        "ammonium",
        "disodium",
        "dipotassium",
        "trisodium",
        "tripotassium",
        "tetrasodium",
        "tetrapotassium",
        "trisalts",  # rare
    )
    is_cation_salt = t.startswith(_CATION_PREFIXES) or any(f" {_c} " in f" {t} " for _c in _CATION_PREFIXES)
    # If the presence of a cation is explicit and the name ends in a salt-like suffix, treat as Salt.
    if is_cation_salt and t.split() and t.split()[-1].endswith(("ate", "ite", "ide", "urate")):
        return "Salt", "Solid"
    if any(t.endswith(suffix) for suffix in ("lactate", "citrate", "gluconate", "succinate", "octenylsuccinate", "propionate")):
        return ("Salt", "Solid") if is_cation_salt else ("Ester", "Liquid")
    if t.endswith(" acetate"):
        # "Geranyl acetate" etc are esters; "Sodium acetate" etc are salts.
        return ("Salt", "Solid") if is_cation_salt else ("Ester", "Liquid")
    if any(t.endswith(f" {suffix}") or t.endswith(suffix) for suffix in ("stearate", "palmitate", "oleate", "myristate", "laurate")):
        return "Esters", "Solid"
    # Generic ester catch-all (many aroma chemicals): "...ate" at end.
    if t.endswith("ate") and not is_cation_salt:
        return "Ester", "Liquid"

    # Generic "salt" token at end (common in TGSC, e.g., "acetic acid, copper salt,")
    if t.endswith(" salt") or t.endswith(" salts"):
        return "Salt", "Solid"

    # Triglycerides
    if "triglyceride" in t or "triglycerides" in t:
        return "Triglyceride", "Oil"
    if "glyceride" in t or "glycerides" in t:
        return "Glycerides", "Oil"

    if re.search(r"\bpca\b", t):
        return "PCA", "Solid"

    # Common chemical family suffixes (helps classify remaining null-variation chemicals)
    if t.endswith(" acid"):
        return "Acid", "Solid"
    if t.endswith(" acids"):
        return "Acid", "Solid"
    if t.endswith(" alcohol"):
        return "Alcohol", "Liquid"
    if t.endswith(" aldehyde"):
        return "Aldehyde", "Liquid"
    if t.endswith(" ketone"):
        return "Ketone", "Liquid"
    if t.endswith(" ether"):
        return "Ether", "Liquid"
    if t.endswith(" acetal") or " acetal " in f" {t} ":
        return "Acetal", "Liquid"
    if t.endswith(" lactone"):
        return "Lactone", "Liquid"
    if t.endswith(" epoxide"):
        return "Epoxide", "Liquid"
    if t.endswith(" anhydride"):
        return "Anhydride", "Solid"
    if t.endswith(" mercaptan"):
        return "Mercaptan", "Liquid"
    if t.endswith(" disulfide"):
        return "Disulfide", "Liquid"
    if t.endswith(" amine"):
        return "Amine", "Liquid"
    if t.endswith("amine"):
        return "Amine", "Liquid"
    if t.endswith(" amide"):
        return "Amide", "Solid"
    if t.endswith("imidazoline"):
        return "Imidazoline", "Liquid"
    if t.endswith(" glycol") or t.endswith("glycol"):
        return "Glycol", "Liquid"

    # Alkanolamides / alkanolamine salts (common surfactant intermediates)
    if t.endswith(" mea") or t.endswith(" dea") or t.endswith(" mipa"):
        return "Alkanolamide", "Liquid"

    # Silicone families
    if "methicone" in t:
        return "Silicone", "Liquid"

    # Single-token chemical family suffixes (e.g., BENZOPHENONE, LIMONENE, GERANIOL)
    if " " not in t and "/" not in t:
        if t.endswith("ol") and len(t) > 5:
            return "Alcohol", "Liquid"
        if t.endswith("one") and len(t) > 6:
            return "Ketone", "Liquid"
        if t.endswith("al") and len(t) > 5:
            return "Aldehyde", "Liquid"
        if t.endswith("ene") and len(t) > 6:
            return "Alkene", "Liquid"
        if t.endswith("ine") and len(t) > 6:
            return "Amine", "Liquid"
        if t.endswith("amide") and len(t) > 8:
            return "Amide", "Solid"
        if t.endswith("acid") and len(t) > 7:
            return "Acid", "Solid"

    # Colorants/dyes markers (very common in INCI)
    if re.match(r"^\s*ci\s*\d+", t) or t.startswith("pigment ") or t.startswith("basic "):
        return "Colorant", "Solid"
    # Common dye naming family in CosIng (e.g., "DIRECT RED 81")
    if t.startswith("direct ") and any(ch.isdigit() for ch in t):
        return "Colorant", "Solid"
    if t.startswith("solvent ") and any(ch.isdigit() for ch in t):
        return "Colorant", "Solid"
    if t.startswith("hc ") and any(ch.isdigit() for ch in t):
        return "Colorant", "Solid"

    # Inorganic salts (only when the word is at the end; avoids over-tagging mid-string).
    if any(
        t.endswith(f" {suffix}") or t == suffix
        for suffix in (
            "chloride",
            "chlorite",
            "chlorate",
            "perchlorate",
            "hypochlorite",
            "hydrochloride",
            "hcl",
            "sulfate",
            "sulfide",
            "silicate",
            "phosphate",
            "carbonate",
            "hydroxide",
            "nitrate",
            "bromide",
            "iodide",
        )
    ):
        return "Salt", "Solid"

    # Oxides / dioxides / peroxides (common mineral families; do NOT treat as amine oxide).
    if t.endswith(" peroxide") or t.endswith(" peroxides"):
        return "Peroxide", "Solid"
    if t.endswith(" dioxide") or t.endswith(" dioxides"):
        return "Dioxide", "Solid"
    if t.endswith(" oxide") or t.endswith(" oxides"):
        return "Oxide", "Solid"

    # Oil fractions
    if "unsaponifiables" in t or "unsaponifiable" in t:
        return "Unsaponifiables", "Oil"

    # Proteins/peptides (common actives) - helps keep these from staying totally untyped.
    if "peptide" in t or "polypeptide" in t:
        return "Peptide", "Solid"
    if "enzyme" in t:
        return "Enzyme", "Solid"
    if t.endswith(" protein") or t.endswith(" proteins"):
        return "Protein", "Solid"
    if t.endswith(" albumin"):
        return "Protein", "Solid"
    if t.endswith(" elastin"):
        return "Protein", "Solid"
    if t.endswith(" lipids") or " lipids" in f" {t} ":
        return "Lipids", "Oil"
    if t.endswith(" dna") or " dna" in f" {t} ":
        return "DNA", "Solid"
    if t.endswith(" sap") or " sap" in f" {t} ":
        return "Sap", "Liquid"

    return "", ""


@dataclass(frozen=True)
class ParsedItem:
    raw_name: str
    definition_term: str
    origin: str
    ingredient_category: str
    refinement_level: str

