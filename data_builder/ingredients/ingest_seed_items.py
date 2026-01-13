"""Seed file ingestion for app seeder JSON files.

This script reads the seed JSON files from app/seeders/globallist/ingredients/categories/
and writes them into the database as source_items with proper parsing,
ensuring they match the same derivation pattern as CosIng/TGSC source data.

Key difference from CosIng/TGSC: seed items have rich spec data (SAP values, iodine, density, etc.)
that should be preserved in derived_specs_json. Also, seed item names are simpler maker-friendly
names like "Shea Butter" rather than INCI names like "BUTYROSPERMUM PARKII (SHEA) BUTTER".
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from . import database_manager
from .item_parser import (
    extract_plant_part,
    infer_origin,
    infer_primary_category,
    infer_refinement,
)

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

_FORM_TOKENS = {
    "oil", "butter", "wax", "powder", "extract", "tincture", "hydrosol",
    "absolute", "concrete", "resin", "gum", "solution", "distillate",
    "concentrate", "flour", "granules", "flakes", "crystals", "chips",
    "shreds", "ribbons", "paste", "cream", "gel", "liquid", "solid",
    "clay", "glycerite",
}

_VARIATION_TOKENS = {
    "refined", "unrefined", "virgin", "extra virgin", "cold pressed",
    "expeller pressed", "organic", "raw", "deodorized", "bleached",
    "hydrogenated", "fractionated", "stabilized", "pasteurized",
    "essential", "fragrance", "carrier", "high oleic", "low linoleic",
}

_INLINE_VARIATION_TOKENS = {"essential", "fragrance", "carrier"}

_PAREN_RE = re.compile(r"\s*\([^)]+\)\s*")
_SPACE_RE = re.compile(r"\s+")
_PERCENTAGE_RE = re.compile(r"\s+(\d+(?:\.\d+)?%)")


def _parse_seed_name(raw_name: str, physical_form_explicit: str = "") -> tuple[str, str, str]:
    """Parse a seed item name into (term, variation, physical_form).
    
    Seed names are simpler maker-friendly names:
    - "Shea Butter" -> ("Shea", "", "Butter")
    - "Olive Oil (Extra Virgin)" -> ("Olive", "Extra Virgin", "Oil")
    - "Sweet Almond Oil" -> ("Sweet Almond", "", "Oil")
    - "Coconut Oil, Refined" -> ("Coconut", "Refined", "Oil")
    - "Salicylic Acid 2% Solution" -> ("Salicylic Acid", "2%", "Solution")
    """
    name = (raw_name or "").strip()
    if not name:
        return "", "", ""
    
    variation = ""
    physical_form = physical_form_explicit or ""
    
    paren_match = re.search(r"\(([^)]+)\)", name)
    if paren_match:
        paren_content = paren_match.group(1).strip()
        paren_lower = paren_content.lower()
        if "%" in paren_content:
            percentage_in_paren = re.search(r"(\d+(?:\.\d+)?%)", paren_content)
            if percentage_in_paren and not variation:
                variation = percentage_in_paren.group(1)
        elif paren_lower in _VARIATION_TOKENS or any(v in paren_lower for v in _VARIATION_TOKENS):
            variation = paren_content
        name = _PAREN_RE.sub(" ", name).strip()
    
    percentage_match = _PERCENTAGE_RE.search(name)
    if percentage_match:
        if not variation:
            variation = percentage_match.group(1)
        name = _PERCENTAGE_RE.sub("", name).strip()
    
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        name = parts[0]
        if len(parts) > 1 and parts[1].lower() in _VARIATION_TOKENS:
            variation = parts[1]
    
    name = _SPACE_RE.sub(" ", name).strip()
    tokens = name.split()
    
    if tokens and tokens[-1].lower() in _FORM_TOKENS:
        if not physical_form:
            physical_form = tokens[-1]
        tokens = tokens[:-1]
    
    if tokens and tokens[-1].lower() in _INLINE_VARIATION_TOKENS:
        if not variation:
            variation = tokens[-1]
        tokens = tokens[:-1]
    
    term = " ".join(tokens).strip()
    
    if not term:
        term = name
    
    return term, variation, physical_form


SEED_CATEGORIES_DIR = Path(__file__).resolve().parents[2] / "app" / "seeders" / "globallist" / "ingredients" / "categories"

SPEC_FIELDS = {
    "saponification_value",
    "iodine_value",
    "melting_point_c",
    "flash_point_c",
    "fatty_acid_profile",
    "comedogenic_rating",
    "recommended_shelf_life_days",
    "density",
    "ph_range",
    "hlb_value",
    "solubility",
    "viscosity",
    "refractive_index",
    "specific_gravity",
    "acid_value",
    "peroxide_value",
    "unsaponifiable_matter",
}


def _sha_key(*parts: str) -> str:
    joined = "|".join([str(p).strip() for p in parts if p is not None])
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def _extract_specs(item: dict[str, Any]) -> dict[str, Any]:
    """Extract specification fields from a seed item."""
    specs = {}
    for field in SPEC_FIELDS:
        if field in item and item[field] is not None:
            specs[field] = item[field]
    return specs


def ingest_seed_items(
    *,
    seed_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Ingest seed items from JSON files, parsing them through item_parser.

    Returns:
        (inserted_source_items, inserted_normalized_terms)
    """
    if seed_dir is None:
        seed_dir = SEED_CATEGORIES_DIR

    if not seed_dir.exists():
        LOGGER.warning(f"Seed directory not found: {seed_dir}")
        return 0, 0

    database_manager.ensure_tables_exist()

    source_rows: list[dict[str, Any]] = []
    normalized_terms: dict[str, dict[str, Any]] = {}

    json_files = sorted(seed_dir.glob("*.json"))
    LOGGER.info(f"Found {len(json_files)} seed JSON files in {seed_dir}")

    for json_path in json_files:
        try:
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            LOGGER.error(f"Failed to parse {json_path}: {e}")
            continue

        category_name = data.get("category_name", json_path.stem)
        items = data.get("items", [])

        for idx, item in enumerate(items):
            raw_name = (item.get("name") or "").strip()
            if not raw_name:
                continue

            inci_name = (item.get("inci_name") or "").strip()
            physical_form_explicit = (item.get("physical_form") or "").strip()

            definition, variation, physical_form = _parse_seed_name(raw_name, physical_form_explicit)

            origin = infer_origin(raw_name)
            ingredient_category = infer_primary_category(definition, origin, raw_name=raw_name) if definition else ""
            refinement_level = infer_refinement(definition or raw_name, raw_name)
            derived_part = extract_plant_part(raw_name)

            specs = _extract_specs(item)

            key = _sha_key("seed", json_path.stem, str(idx), raw_name)
            content_hash = _sha_key("seed", raw_name, inci_name)

            source_row_id = f"seed:{json_path.stem}:{idx}"

            aliases = item.get("aliases", [])
            ingredient_block = item.get("ingredient", {})
            certifications = item.get("certifications", [])

            payload = {
                "seed_file": json_path.name,
                "category_name": category_name,
                "item_index": idx,
                "aliases": aliases,
                "ingredient": ingredient_block,
                "certifications": certifications,
                "default_unit": item.get("default_unit"),
                "is_active_ingredient": item.get("is_active_ingredient", False),
            }

            source_rows.append({
                "key": key,
                "source": "seed",
                "source_row_id": source_row_id,
                "source_row_number": idx,
                "source_ref": str(json_path.relative_to(seed_dir.parent.parent.parent.parent.parent)) if seed_dir else json_path.name,
                "content_hash": content_hash,
                "is_composite": False,
                "raw_name": raw_name,
                "inci_name": inci_name or None,
                "cas_number": None,
                "cas_numbers_json": json.dumps([], ensure_ascii=False),
                "derived_term": definition or None,
                "derived_variation": variation or None,
                "derived_physical_form": physical_form or None,
                "derived_part": derived_part or None,
                "derived_part_reason": "token_in_raw_name" if derived_part else None,
                "derived_specs_json": json.dumps(specs, ensure_ascii=False) if specs else None,
                "origin": origin,
                "ingredient_category": ingredient_category or None,
                "refinement_level": refinement_level or None,
                "status": "linked" if definition else "orphan",
                "needs_review_reason": None if definition else "Unable to derive definition term from seed item",
                "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
            })

            if definition:
                rec = normalized_terms.setdefault(
                    definition,
                    {
                        "term": definition,
                        "seed_category": ingredient_category or None,
                        "botanical_name": "",
                        "inci_name": "",
                        "cas_number": "",
                        "description": "",
                        "ingredient_category": ingredient_category or None,
                        "origin": origin,
                        "refinement_level": refinement_level,
                        "derived_from": "",
                        "ingredient_category_confidence": 80,
                        "origin_confidence": 80,
                        "refinement_confidence": 80,
                        "derived_from_confidence": 0,
                        "overall_confidence": 80,
                        "sources_json": json.dumps({"sources": ["seed"]}, ensure_ascii=False, sort_keys=True),
                    },
                )
                if inci_name and not rec.get("inci_name"):
                    rec["inci_name"] = inci_name

    if dry_run:
        LOGGER.info(f"[DRY RUN] Would insert {len(source_rows)} source items, {len(normalized_terms)} normalized terms")
        for row in source_rows[:10]:
            LOGGER.info(f"  -> {row['raw_name']} => term={row['derived_term']}, var={row['derived_variation']}, form={row['derived_physical_form']}")
        return len(source_rows), len(normalized_terms)

    with database_manager.get_session() as session:
        for row in source_rows:
            existing = session.query(database_manager.SourceItem).filter_by(key=row["key"]).first()
            if existing:
                for k, v in row.items():
                    setattr(existing, k, v)
            else:
                session.add(database_manager.SourceItem(**row))

        for term, rec in normalized_terms.items():
            existing = session.query(database_manager.NormalizedTerm).filter_by(term=term).first()
            if not existing:
                session.add(database_manager.NormalizedTerm(**rec))

        session.commit()

    LOGGER.info(f"Ingested {len(source_rows)} seed source items, {len(normalized_terms)} normalized terms")
    return len(source_rows), len(normalized_terms)


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Ingest seed JSON files into source_items")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB, just show what would be inserted")
    parser.add_argument("--seed-dir", type=Path, help="Override seed directory path")

    args = parser.parse_args()

    inserted, terms = ingest_seed_items(
        seed_dir=args.seed_dir,
        dry_run=args.dry_run,
    )

    print(f"Inserted {inserted} source items, {terms} normalized terms")


if __name__ == "__main__":
    main()
