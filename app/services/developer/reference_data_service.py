from __future__ import annotations

from typing import Dict, List

from app.extensions import db
from app.models import GlobalItem
from app.utils.settings import get_settings, save_settings


def read_json_file(*_args, **_kwargs):
    """Backward-compatible shim for tests; reads from app settings DB."""
    return get_settings()


def write_json_file(_path, data):
    """Backward-compatible shim for tests; writes to app settings DB."""
    save_settings(data)


class ReferenceDataService:
    """Helpers for curated container lists and reference data."""

    DEFAULTS = {
        "materials": [
            "Glass",
            "PET Plastic",
            "HDPE Plastic",
            "PP Plastic",
            "Aluminum",
            "Tin",
            "Steel",
            "Paperboard",
            "Cardboard",
            "Silicone",
        ],
        "types": [
            "Jar",
            "Bottle",
            "Tin",
            "Tube",
            "Pump Bottle",
            "Spray Bottle",
            "Dropper Bottle",
            "Roll-on Bottle",
            "Squeeze Bottle",
            "Vial",
        ],
        "styles": [
            "Boston Round",
            "Straight Sided",
            "Wide Mouth",
            "Narrow Mouth",
            "Cobalt Blue",
            "Amber",
            "Clear",
            "Frosted",
        ],
        "colors": [
            "Clear",
            "Amber",
            "Cobalt Blue",
            "Green",
            "White",
            "Black",
            "Frosted",
            "Silver",
            "Gold",
        ],
    }

    @staticmethod
    def load_curated_container_lists() -> Dict[str, List[str]]:
        settings = read_json_file("settings.json", default={}) or {}
        curated_lists = settings.get("container_management", {}).get("curated_lists", {})
        if curated_lists and all(key in curated_lists for key in ReferenceDataService.DEFAULTS.keys()):
            return curated_lists
        return ReferenceDataService._build_default_lists()

    @staticmethod
    def save_curated_container_lists(curated_lists: Dict[str, List[str]]) -> None:
        settings = read_json_file("settings.json", default={}) or {}
        settings.setdefault("container_management", {})["curated_lists"] = curated_lists
        write_json_file("settings.json", settings)

    @staticmethod
    def _build_default_lists() -> Dict[str, List[str]]:
        defaults = {key: list(values) for key, values in ReferenceDataService.DEFAULTS.items()}

        materials = (
            db.session.query(GlobalItem.container_material)
            .filter(GlobalItem.container_material.isnot(None))
            .distinct()
            .all()
        )
        types = (
            db.session.query(GlobalItem.container_type)
            .filter(GlobalItem.container_type.isnot(None))
            .distinct()
            .all()
        )
        styles = (
            db.session.query(GlobalItem.container_style)
            .filter(GlobalItem.container_style.isnot(None))
            .distinct()
            .all()
        )
        colors = (
            db.session.query(GlobalItem.container_color)
            .filter(GlobalItem.container_color.isnot(None))
            .distinct()
            .all()
        )

        def merge(existing: List[str], values):
            existing.extend([val[0] for val in values if val[0]])
            return sorted(list(set(existing)))

        defaults["materials"] = merge(defaults["materials"], materials)
        defaults["types"] = merge(defaults["types"], types)
        defaults["styles"] = merge(defaults["styles"], styles)
        defaults["colors"] = merge(defaults["colors"], colors)
        return defaults
