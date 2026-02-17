from __future__ import annotations

from typing import Any, Dict, List

USE_CASE_MAP = {
    "ingredient": [
        "Lock formulas to a single density source for accurate conversions.",
        "Share canonical naming (INCI + aliases) with every teammate.",
        "Drive costing models with consistent default units.",
    ],
    "container": [
        "Standardize fill volumes and capacity planning across recipes.",
        "Model packaging BOMs with reliable measurements.",
        "Recommend compatible lids, pumps, or closures as metadata grows.",
    ],
    "packaging": [
        "Track finished goods packaging across SKUs.",
        "Bundle inserts, boxes, and wraps to each product workflow.",
        "Link packaging specs to suppliers for automated reorders.",
    ],
    "consumable": [
        "Forecast recurring shop supplies and cleaning materials.",
        "Bake non-inventory consumables into batch costing.",
        "Assign safety / handling instructions to recurring tasks.",
    ],
}


class GlobalItemMetadataService:
    """Generate SEO + descriptive metadata for Global Items on demand."""

    @staticmethod
    def _get_type_label(item) -> str:
        if not getattr(item, "item_type", None):
            return "Item"
        return item.item_type.replace("_", " ").title()

    @staticmethod
    def _build_summary(item) -> str:
        type_label = GlobalItemMetadataService._get_type_label(item)
        category = getattr(getattr(item, "ingredient_category", None), "name", None)
        density = f"{item.density:.3f} g/mL" if item.density else None
        default_unit = item.default_unit or "gram"
        parts: List[str] = [f"{item.name} is a {type_label.lower()} reference"]
        if category:
            parts.append(f"in the {category} category")
        parts.append("within the BatchTrack global library.")
        summary = " ".join(parts)
        summary += f" It defaults to {default_unit} units"
        if density:
            summary += f" with a working density of {density}"
        summary += "."
        return summary

    @staticmethod
    def _build_meta_description(item) -> str:
        type_label = GlobalItemMetadataService._get_type_label(item)
        density = f"{item.density:.3f} g/mL" if item.density else None
        capacity = None
        if item.capacity:
            unit = item.capacity_unit or ""
            capacity = f"{item.capacity:g} {unit}".strip()
        snippets = [
            f"{item.name} {type_label.lower()} specs from the BatchTrack global inventory library.",
            "Includes default units, aliases, and adoption insights.",
        ]
        if density:
            snippets.append(f"Density: {density}.")
        if capacity:
            snippets.append(f"Capacity: {capacity}.")
        return " ".join(snippets)

    @staticmethod
    def _build_guidance(item) -> str:
        paragraphs = [
            f"<p>BatchTrack tracks {item.name} as a canonical {item.item_type} so every recipe, batch, and inventory transfer references the same data.</p>",
            "<p>Use the global library entry to power public calculators, onboarding checklists, and any automation that needs a trusted baseline.</p>",
        ]
        if item.default_is_perishable:
            shelf = (
                f"{item.recommended_shelf_life_days} days"
                if item.recommended_shelf_life_days
                else "its documented shelf life"
            )
            paragraphs.append(
                f"<p>Mark storage locations and FIFO handling instructions—this item is flagged as perishable with a default lifecycle of {shelf}.</p>"
            )
        else:
            paragraphs.append(
                "<p>Assign suppliers, pricing tiers, and QA docs inside BatchTrack to fully operationalize this record.</p>"
            )
        return "\n".join(paragraphs)

    @staticmethod
    def _build_faqs(item) -> List[Dict[str, str]]:
        faqs = [
            {
                "question": f"What is the default unit for {item.name}?",
                "answer": f"{item.name} uses {item.default_unit or 'gram'} by default so calculations stay consistent across recipes.",
            },
            {
                "question": f"How is {item.name} used inside BatchTrack?",
                "answer": "Teams link this global item to inventory, recipes, and public tools so updates to specs or costs flow everywhere automatically.",
            },
        ]
        if item.density:
            faqs.append(
                {
                    "question": f"What density should I use for {item.name}?",
                    "answer": f"BatchTrack stores a working density of {item.density:.3f} g/mL for this entry. Override it per-organization if your supplier provides a different spec.",
                }
            )
        if item.default_is_perishable and item.recommended_shelf_life_days:
            faqs.append(
                {
                    "question": f"What is the recommended shelf life for {item.name}?",
                    "answer": f"The default shelf life is {item.recommended_shelf_life_days} days. Adjust it per location if lab results differ.",
                }
            )
        return faqs

    @staticmethod
    def generate_defaults(item) -> Dict[str, Any]:
        type_label = GlobalItemMetadataService._get_type_label(item)
        use_cases = list(USE_CASE_MAP.get(item.item_type, USE_CASE_MAP["ingredient"]))
        return {
            "meta_title": f"{item.name} — {type_label} Specs",
            "meta_description": GlobalItemMetadataService._build_meta_description(item),
            "summary": GlobalItemMetadataService._build_summary(item),
            "use_cases": use_cases,
            "guidance": GlobalItemMetadataService._build_guidance(item),
            "faqs": GlobalItemMetadataService._build_faqs(item),
        }

    @staticmethod
    def merge_metadata(item) -> Dict[str, Any]:
        existing = dict(item.metadata_json or {})
        defaults = GlobalItemMetadataService.generate_defaults(item)
        merged = dict(existing)
        for key, value in defaults.items():
            if not merged.get(key):
                merged[key] = value
        return merged
