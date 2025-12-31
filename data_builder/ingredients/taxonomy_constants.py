"""Curated taxonomy constants for the ingredient lineage tree.

Design intent (data_builder only):
- Origin: upstream provenance bucket (single-select).
- Ingredient category: second-level material family under an origin (single-select).
- Master categories: UX groupings (multi-select) derived from category/form/variation/functions/apps.

This file also contains lightweight guardrails used by the normalizer/compiler to:
- constrain/refine category assignments
- constrain refinement levels by category
- pre-approve common variation tokens that are structurally important (to avoid mass quarantine)
"""

from __future__ import annotations

# Ingredient categories (second level under Origin; single-select).
#
# Notes:
# - The original 16 plant/mineral families remain.
# - We add a small set of non-plant families so synthetics/ferments don't get forced into "Herbs".
# - These are NOT UX groupings; UX is handled by MASTER_CATEGORIES + derivation rules.
INGREDIENT_CATEGORIES_PRIMARY: list[str] = [
    # Plant-derived families
    "Fruits & Berries",
    "Vegetables",
    "Grains",
    "Nuts",
    "Seeds",
    "Spices",
    "Herbs",
    "Flowers",
    "Roots",
    "Barks",
    "Fibers",
    # Mineral/Earth families
    "Clays",
    "Minerals",
    "Salts",
    # Cross-domain families
    "Sugars",
    "Liquid Sweeteners",
    "Acids",
    # Synthetic families (minimal but necessary for INCI-scale coverage)
    "Synthetic - Polymers",
    "Synthetic - Surfactants",
    "Synthetic - Solvents",
    "Synthetic - Preservatives",
    "Synthetic - Colorants",
    "Synthetic - Salts & Bases",
    "Synthetic - Actives",
    "Synthetic - Other",
    # Fermentation families (minimal)
    "Fermentation - Acids",
    "Fermentation - Polysaccharides",
    "Fermentation - Actives",
    "Fermentation - Other",
    # Animal families (minimal; can be expanded later)
    "Animal - Fats",
    "Animal - Proteins",
    "Animal - Fibers",
    "Animal - Dairy",
    "Animal - Other",
    # Marine families (minimal)
    "Marine - Botanicals",
    "Marine - Minerals",
    "Marine - Other",
]

# Master Categories (UX dropdown multi-select; curated group).
# NOTE: user-provided list exceeds "28"; we keep exactly as provided.
MASTER_CATEGORIES: list[str] = [
    "Fruits & Berries",
    "Vegetables",
    "Grains & Starches",
    "Nuts",
    "Seeds",
    "Spices",
    "Herbs",
    "Flowers",
    "Roots",
    "Barks",
    "Oils & Fats",
    "Carriers",
    "Butters",
    "Waxes",
    "Essential Oils",
    "Extracts",
    "Absolutes",
    "Concretes",
    "Resins & Gums",
    "Hydrosols",
    "Clays",
    "Minerals",
    "Salts",
    "Colorants & Pigmants",
    "Preservatives & Antioxidants",
    "Surfactants & Cleansers",
    "Emulsifiers & Stabilizers",
    "Thickeners & Gelling Agents",
    "Fermentation Starters",
    "Sugars",
    "Liquid Sweeteners",
    "Acids & PH Adjusters",
]

ORIGINS: list[str] = [
    "Plant-Derived",
    "Animal-Derived",
    "Animal-Byproduct",
    "Mineral/Earth",
    "Synthetic",
    "Fermentation",
    "Marine-Derived",
]

# Origin -> allowed ingredient categories (guardrail).
# This keeps the lineage tree smooth and prevents nonsense pairings.
ORIGIN_TO_INGREDIENT_CATEGORIES: dict[str, list[str]] = {
    "Plant-Derived": [
        "Fruits & Berries",
        "Vegetables",
        "Grains",
        "Nuts",
        "Seeds",
        "Spices",
        "Herbs",
        "Flowers",
        "Roots",
        "Barks",
        "Fibers",
        "Sugars",
        "Liquid Sweeteners",
        "Acids",
    ],
    "Mineral/Earth": [
        "Clays",
        "Minerals",
        "Salts",
        "Acids",
    ],
    "Animal-Derived": [
        "Animal - Fats",
        "Animal - Proteins",
        "Animal - Fibers",
        "Animal - Dairy",
        "Animal - Other",
    ],
    "Animal-Byproduct": [
        "Animal - Fats",
        "Animal - Proteins",
        "Animal - Fibers",
        "Animal - Dairy",
        "Animal - Other",
    ],
    "Synthetic": [
        "Synthetic - Polymers",
        "Synthetic - Surfactants",
        "Synthetic - Solvents",
        "Synthetic - Preservatives",
        "Synthetic - Colorants",
        "Synthetic - Salts & Bases",
        "Synthetic - Actives",
        "Synthetic - Other",
        # synthetic acids/salts can still be treated as acids/salts at the category level if desired
        "Acids",
        "Salts",
    ],
    "Fermentation": [
        "Fermentation - Acids",
        "Fermentation - Polysaccharides",
        "Fermentation - Actives",
        "Fermentation - Other",
        "Acids",
    ],
    "Marine-Derived": [
        "Marine - Botanicals",
        "Marine - Minerals",
        "Marine - Other",
        "Salts",
    ],
}

# Category -> allowed refinement levels (guardrail). Omitted categories accept any refinement.
# This is intentionally minimal and can be expanded as you approve lineage semantics.
CATEGORY_ALLOWED_REFINEMENT_LEVELS: dict[str, set[str]] = {
    # Plant/mineral staples
    "Grains": {"Raw/Unprocessed", "Minimally Processed", "Milled/Ground", "Other"},
    "Nuts": {"Raw/Unprocessed", "Minimally Processed", "Extracted Fat", "Other"},
    "Seeds": {"Raw/Unprocessed", "Minimally Processed", "Extracted Fat", "Other"},
    "Fibers": {"Raw/Unprocessed", "Minimally Processed", "Milled/Ground", "Other"},
    "Clays": {"Raw/Unprocessed", "Other"},
    "Minerals": {"Raw/Unprocessed", "Other"},
    "Salts": {"Raw/Unprocessed", "Other"},
    "Acids": {"Other", "Fermented", "Synthesized"},
    # Synthetic
    "Synthetic - Polymers": {"Synthesized", "Other"},
    "Synthetic - Surfactants": {"Synthesized", "Other"},
    "Synthetic - Solvents": {"Synthesized", "Other"},
    "Synthetic - Preservatives": {"Synthesized", "Other"},
    "Synthetic - Colorants": {"Synthesized", "Other"},
    "Synthetic - Salts & Bases": {"Synthesized", "Other"},
    "Synthetic - Actives": {"Synthesized", "Other"},
    "Synthetic - Other": {"Synthesized", "Other"},
    # Fermentation
    "Fermentation - Acids": {"Fermented", "Other"},
    "Fermentation - Polysaccharides": {"Fermented", "Other"},
    "Fermentation - Actives": {"Fermented", "Other"},
    "Fermentation - Other": {"Fermented", "Other"},
    # Animal
    "Animal - Fibers": {"Raw/Unprocessed", "Minimally Processed", "Other"},
}

REFINEMENT_LEVELS: list[str] = [
    "Raw/Unprocessed",
    "Minimally Processed",
    "Extracted/Distilled",
    "Milled/Ground",
    "Fermented",
    "Synthesized",
    "Extracted Fat",
    "Other",
]

# Item-level curated variations (grows with review).
VARIATIONS_CURATED: list[str] = [
    "Essential",
    "CO2 Extracted",
    "Raw",
    "2%",
    "Granulated",
    "Refined",
    "Unrefined",
    "White",
    "Whole",
    "Brown",
    "Dutch-Processed",
    "Organic",
    "Filtered",
    "Unsweetened",
    "Cold-Pressed",
    "Steam-Distilled",
    "Micronized",
    "Nano",
    "Food-Grade",
    "Barista",
    "Low-Fat",
    "Reduced",
    "Crystallized",
    "Powdered",
    "Chunky",
    "Cinnamon",
    "Salted",
    "Anhydrous",
    "Hydrous",
    "Creamed",
    "Fair Trade",
    "Kosher",
    "GMO-Free",
    "Grade A",
    "Sweet",
    "Bitter",
    "Kappa",
    "Methylcobalamin",
    "Hydrated",
    "Unbleached",
    "Bleached",
    "Whole Grain",
    "Enriched",
    "Fortified",
    "Instant",
    "Slow-Rise",
    "Active Dry",
    "Fresh",
    # Structural variations used for master-category derivation / item modeling.
    # These are distinct from physical_form and may appear as the purchasable "type".
    "Oil",
    "Butter",
    "Wax",
    "Essential Oil",
    "CO2 Extract",
    "Extract",
    "Absolute",
    "Concrete",
    # Plant-part / material qualifiers that appear constantly in INCI/TGSC item names.
    # Keeping these pre-approved prevents mass quarantine when the compiler extracts them.
    "Leaf",
    "Needle",
    "Cone",
    "Seed",
    "Kernel",
    "Nut",
    "Fruit",
    "Berry",
    "Flower",
    "Root",
    "Bark",
    "Wood",
]

PHYSICAL_FORMS: list[str] = [
    "Whole",
    "Slices",
    "Diced",
    "Chopped",
    "Minced",
    "Crushed",
    "Ground",
    "Powder",
    "Granules",
    "Flakes",
    "Shreds",
    "Ribbons",
    "Pellets",
    "Chips",
    "Nib",
    "Buds",
    "Flowers",
    "Leaves",
    "Needles",
    "Stems",
    "Bark",
    "Resin",
    "Gum",
    "Latex",
    "Sap",
    "Juice",
    "Puree",
    "Paste",
    "Concentrate",
    "Syrup",
    "Infusion",
    "Decoction",
    "Tincture",
    "Hydrosol",
    "Oil",
    "Butter",
    "Wax",
    "Crystals",
    "Isolate",
    "Emulsion",
]

# Seeded rules that connect existing vocab into the Master Categories (UX group).
# Each tuple: (master_category, source_type, source_value)
# source_type in: ingredient_category | variation | physical_form | function_tag | application
MASTER_CATEGORY_RULE_SEED: list[tuple[str, str, str]] = [
    # Ingredient category -> master category (identity, with a couple of remaps)
    ("Fruits & Berries", "ingredient_category", "Fruits & Berries"),
    ("Vegetables", "ingredient_category", "Vegetables"),
    ("Grains & Starches", "ingredient_category", "Grains"),
    ("Nuts", "ingredient_category", "Nuts"),
    ("Seeds", "ingredient_category", "Seeds"),
    ("Spices", "ingredient_category", "Spices"),
    ("Herbs", "ingredient_category", "Herbs"),
    ("Flowers", "ingredient_category", "Flowers"),
    ("Roots", "ingredient_category", "Roots"),
    ("Barks", "ingredient_category", "Barks"),
    ("Clays", "ingredient_category", "Clays"),
    ("Minerals", "ingredient_category", "Minerals"),
    ("Salts", "ingredient_category", "Salts"),
    ("Sugars", "ingredient_category", "Sugars"),
    ("Liquid Sweeteners", "ingredient_category", "Liquid Sweeteners"),
    ("Acids & PH Adjusters", "ingredient_category", "Acids"),

    # Physical forms -> master categories
    ("Oils & Fats", "physical_form", "Oil"),
    ("Carriers", "physical_form", "Oil"),
    ("Butters", "physical_form", "Butter"),
    ("Waxes", "physical_form", "Wax"),
    ("Hydrosols", "physical_form", "Hydrosol"),
    ("Resins & Gums", "physical_form", "Resin"),
    ("Resins & Gums", "physical_form", "Gum"),

    # Variations -> master categories
    ("Essential Oils", "variation", "Essential Oil"),
    ("Essential Oils", "variation", "Steam-Distilled"),
    ("Extracts", "variation", "CO2 Extracted"),
    ("Extracts", "variation", "CO2 Extract"),
    ("Extracts", "variation", "Extract"),
    ("Absolutes", "variation", "Absolute"),
    ("Concretes", "variation", "Concrete"),

    # Function tags -> master categories
    ("Colorants & Pigmants", "function_tag", "Colorant"),
    ("Preservatives & Antioxidants", "function_tag", "Preservative"),
    ("Preservatives & Antioxidants", "function_tag", "Antioxidant"),
    ("Surfactants & Cleansers", "function_tag", "Surfactant"),
    ("Emulsifiers & Stabilizers", "function_tag", "Emulsifier"),
    ("Emulsifiers & Stabilizers", "function_tag", "Stabilizer"),
    ("Thickeners & Gelling Agents", "function_tag", "Thickener"),
]

