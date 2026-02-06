"""Config schema: Feature flag settings.

Synopsis:
Defines feature toggle keys used to enable or disable capabilities.

Glossary:
- Feature flag: Config-driven toggle that controls product behavior.
"""

# --- Feature fields ---
# Purpose: Provide feature flag configuration definitions.
FIELDS = [
    {
        "key": "FEATURE_INVENTORY_ANALYTICS",
        "cast": "bool",
        "default": True,
        "description": "Enable inventory analytics feature.",
        "recommended": "true",
    },
    {
        "key": "FEATURE_BATCHBOT",
        "cast": "bool",
        "default": True,
        "description": "Master toggle for BatchBot features.",
        "recommended": "true",
    },
]

# --- Feature section ---
# Purpose: Provide section metadata for integrations checklist grouping.
SECTION = {
    "key": "features",
    "title": "Feature Flags",
    "note": "Optional feature toggles.",
}
