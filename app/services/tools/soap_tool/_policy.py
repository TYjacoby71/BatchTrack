"""Soap tool policy constants shared across service and frontend.

Synopsis:
Defines centralized soap-tool policy values (quality ranges, presets, category
filters, and display configuration) so the frontend can consume backend-owned
configuration without hardcoding domain constants in JS modules.

Glossary:
- Policy payload: JSON-safe dictionary injected into the soap tool page.
"""

from __future__ import annotations

QUALITY_RANGES = {
    "hardness": (29.0, 54.0),
    "cleansing": (12.0, 22.0),
    "conditioning": (44.0, 69.0),
    "bubbly": (14.0, 46.0),
    "creamy": (16.0, 48.0),
}

QUALITY_HINTS = {
    "hardness": "Durable bar that resists mush.",
    "cleansing": "Higher values feel more stripping.",
    "conditioning": "Silky, moisturizing feel.",
    "bubbly": "Fluffy lather and big bubbles.",
    "creamy": "Stable, creamy lather.",
}

QUALITY_FEEL_HINTS = {
    "hardness": {
        "low": "Soft bar, slower unmold.",
        "ok": "Balanced hardness for daily use.",
        "high": "Very hard bar, can feel brittle.",
    },
    "cleansing": {
        "low": "Very mild cleansing.",
        "ok": "Balanced cleansing.",
        "high": "Strong cleansing, can be drying.",
    },
    "conditioning": {
        "low": "Less conditioning feel.",
        "ok": "Smooth and conditioning.",
        "high": "Very conditioning, may feel oily.",
    },
    "bubbly": {
        "low": "Low bubbly lather.",
        "ok": "Balanced bubbly lather.",
        "high": "Very bubbly, big foam.",
    },
    "creamy": {
        "low": "Light creamy lather.",
        "ok": "Creamy and stable.",
        "high": "Dense creamy lather.",
    },
}

IODINE_RANGE = (41.0, 70.0)
IODINE_SCALE_MAX = 100.0
INS_RANGE = (136.0, 170.0)
INS_SCALE_MAX = 250.0

QUALITY_BASE = {
    key: (bounds[0] + bounds[1]) / 2.0
    for key, bounds in QUALITY_RANGES.items()
}

QUALITY_PRESETS = {
    "balanced": {
        "hardness": 40,
        "cleansing": 15,
        "conditioning": 55,
        "bubbly": 25,
        "creamy": 25,
        "iodine": 55,
        "ins": 160,
    },
    "bubbly": {
        "hardness": 35,
        "cleansing": 20,
        "conditioning": 50,
        "bubbly": 35,
        "creamy": 25,
        "iodine": 60,
        "ins": 150,
    },
    "creamy": {
        "hardness": 45,
        "cleansing": 12,
        "conditioning": 60,
        "bubbly": 20,
        "creamy": 35,
        "iodine": 50,
        "ins": 155,
    },
    "hard": {
        "hardness": 50,
        "cleansing": 18,
        "conditioning": 48,
        "bubbly": 22,
        "creamy": 28,
        "iodine": 45,
        "ins": 165,
    },
    "gentle": {
        "hardness": 35,
        "cleansing": 10,
        "conditioning": 65,
        "bubbly": 15,
        "creamy": 20,
        "iodine": 65,
        "ins": 140,
    },
    "castile": {
        "hardness": 20,
        "cleansing": 5,
        "conditioning": 75,
        "bubbly": 10,
        "creamy": 15,
        "iodine": 80,
        "ins": 110,
    },
    "shampoo": {
        "hardness": 30,
        "cleansing": 22,
        "conditioning": 50,
        "bubbly": 30,
        "creamy": 25,
        "iodine": 60,
        "ins": 145,
    },
    "utility": {
        "hardness": 70,
        "cleansing": 50,
        "conditioning": 20,
        "bubbly": 50,
        "creamy": 20,
        "iodine": 10,
        "ins": 250,
    },
    "luxury": {
        "hardness": 55,
        "cleansing": 10,
        "conditioning": 55,
        "bubbly": 15,
        "creamy": 40,
        "iodine": 50,
        "ins": 150,
    },
    "palmFree": {
        "hardness": 42,
        "cleansing": 16,
        "conditioning": 58,
        "bubbly": 22,
        "creamy": 28,
        "iodine": 55,
        "ins": 155,
    },
}

FATTY_BAR_COLORS = {
    "lauric": "var(--color-primary)",
    "myristic": "var(--color-info)",
    "palmitic": "var(--color-warning)",
    "stearic": "var(--color-muted)",
    "ricinoleic": "var(--color-info-hover)",
    "oleic": "var(--color-success)",
    "linoleic": "var(--color-primary-hover)",
    "linolenic": "var(--color-danger)",
}

FATTY_DISPLAY_KEYS = (
    "lauric",
    "myristic",
    "palmitic",
    "stearic",
    "ricinoleic",
    "oleic",
    "linoleic",
    "linolenic",
)

OIL_TIP_RULES = (
    {
        "pattern": "coconut|palm kernel|babassu|murumuru",
        "flags": "i",
        "tip": "High lauric oils trace fast and feel cleansing; keep superfat >= 5%.",
    },
    {
        "pattern": "olive|avocado|rice bran|canola|sunflower|safflower|almond|apricot|macadamia|camellia|grapeseed|hazelnut",
        "flags": "i",
        "tip": "High-oleic liquid oils trace slowly and stay softer early on; allow a longer cure.",
    },
    {
        "pattern": "castor",
        "flags": "i",
        "tip": "Castor boosts lather but can feel sticky above 10-15%.",
    },
    {
        "pattern": "cocoa|shea|mango|kokum|sal|illipe|tallow|lard|palm|stearic",
        "flags": "i",
        "tip": "Hard fats/butters set up quickly; melt fully and keep batter warm for a smooth pour.",
    },
    {
        "pattern": "beeswax|candelilla|carnauba|wax",
        "flags": "i",
        "tip": "Waxes harden fast and can seize; keep usage low and add hot.",
    },
    {
        "pattern": "hemp|flax|linseed|evening primrose|borage|rosehip|black currant|chia|pomegranate",
        "flags": "i",
        "tip": "High-PUFA oils shorten shelf life; keep low and add antioxidant.",
    },
)

UNIT_FACTORS = {"g": 1.0, "oz": 28.3495, "lb": 453.592}

CITRIC_LYE_FACTORS = {"NaOH": 0.624, "KOH": 0.71}

STAGE_CONFIGS = (
    {"id": 1, "tab_id": "soapStage1Tab", "pane_id": "soapStage1Pane", "required": True},
    {"id": 2, "tab_id": "soapStage2Tab", "pane_id": "soapStage2Pane", "required": True},
    {"id": 3, "tab_id": "soapStage3Tab", "pane_id": "soapStage3Pane", "required": True},
    {"id": 4, "tab_id": "soapStage4Tab", "pane_id": "soapStage4Pane", "required": False},
    {"id": 5, "tab_id": "soapStage5Tab", "pane_id": "soapStage5Pane", "required": False},
)

INGREDIENT_CATEGORY_FILTERS = {
    "oils": ("Oils (Carrier & Fixed)", "Butters & Solid Fats", "Waxes"),
    "fragrances": ("Essential Oils", "Fragrance Oils"),
    "lactate_additives": ("Aqueous Solutions & Blends", "Preservatives & Additives"),
    "sugar_additives": ("Sugars & Syrups",),
    "salt_additives": ("Salts & Minerals",),
    "citric_additives": ("Preservatives & Additives", "Salts & Minerals", "Aqueous Solutions & Blends"),
}

DEFAULT_INPUTS = {
    "unit": "g",
    "mold_oil_pct": 65,
    "mold_shape": "loaf",
    "mold_cylinder_correction": False,
    "mold_cylinder_factor": 0.85,
    "lye_type": "NaOH",
    "water_method": "percent",
    "superfat_pct": 5,
    "lye_purity_pct": 100,
    "water_pct": 33,
    "lye_concentration_pct": 33,
    "water_ratio": 2,
    "additive_lactate_pct": 1,
    "additive_sugar_pct": 1,
    "additive_salt_pct": 0.5,
    "additive_citric_pct": 0,
    "quality_preset": "balanced",
    "fragrance_pct": 3,
}


# --- Frontend policy payload builder ---
# Purpose: Serialize soap policy constants for JS consumption on page render.
# Inputs: None.
# Outputs: JSON-safe policy dictionary for window.soapToolPolicy.
def get_soap_tool_policy() -> dict:
    return {
        "quality_ranges": QUALITY_RANGES,
        "quality_hints": QUALITY_HINTS,
        "quality_feel_hints": QUALITY_FEEL_HINTS,
        "iodine_range": IODINE_RANGE,
        "iodine_scale_max": IODINE_SCALE_MAX,
        "ins_range": INS_RANGE,
        "ins_scale_max": INS_SCALE_MAX,
        "quality_base": QUALITY_BASE,
        "quality_presets": QUALITY_PRESETS,
        "fatty_bar_colors": FATTY_BAR_COLORS,
        "fatty_display_keys": FATTY_DISPLAY_KEYS,
        "oil_tip_rules": OIL_TIP_RULES,
        "unit_factors": UNIT_FACTORS,
        "citric_lye_factors": CITRIC_LYE_FACTORS,
        "stage_configs": STAGE_CONFIGS,
        "ingredient_category_filters": INGREDIENT_CATEGORY_FILTERS,
        "default_inputs": DEFAULT_INPUTS,
    }


__all__ = [
    "QUALITY_RANGES",
    "IODINE_RANGE",
    "INS_RANGE",
    "CITRIC_LYE_FACTORS",
    "DEFAULT_INPUTS",
    "get_soap_tool_policy",
]
