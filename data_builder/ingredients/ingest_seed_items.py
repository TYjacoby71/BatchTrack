"""Seed file ingestion for app seeder JSON files.

This script reads the seed JSON files from app/seeders/globallist/ingredients/categories/
and inserts them into compiler_state.db as source_items.

Key difference from CosIng/TGSC: seed items use maker-friendly names ("Shea Butter")
not INCI names ("BUTYROSPERMUM PARKII (SHEA) BUTTER"), so we use custom parsing
but normalize terms to enable clustering with CosIng/TGSC data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from . import database_manager
from .item_parser import (
    extract_plant_part,
    infer_origin,
    infer_primary_category,
    infer_refinement,
)

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
SEED_CATEGORIES_DIR = BASE_DIR.parents[1] / "app" / "seeders" / "globallist" / "ingredients" / "categories"

SPEC_FIELDS = [
    "density", "sap_value_naoh", "sap_value_koh", "iodine_value",
    "ph_level", "flash_point", "melting_point", "boiling_point",
    "solubility", "hlb_value", "comedogenic_rating", "shelf_life_months",
    "recommended_usage_min", "recommended_usage_max", "recommended_usage_unit",
    "fatty_acid_profile", "vitamin_content", "mineral_content",
    "active_compounds", "contraindications", "storage_requirements",
]

_FORM_TOKENS = {
    "oil", "butter", "wax", "powder", "extract", "tincture", "hydrosol",
    "absolute", "concrete", "resin", "gum", "solution", "distillate",
    "concentrate", "granules", "flakes", "crystals", "chips",
    "shreds", "ribbons", "paste", "cream", "gel", "liquid", "solid",
    "clay", "glycerite", "milk", "water", "juice", "pulp", "puree",
}

_DERIVATIVE_INGREDIENTS = {
    "flour": {"term": "Flour", "physical_form": "Powder"},
    "meal": {"term": "Meal", "physical_form": "Powder"},
    "starch": {"term": "Starch", "physical_form": "Powder"},
    "sugar": {"term": "Sugar", "physical_form": "Granules"},
    "salt": {"term": "Salt", "physical_form": "Granules"},
    "vinegar": {"term": "Vinegar", "physical_form": "Liquid"},
}

_VARIATION_TOKENS = {
    "refined", "unrefined", "virgin", "extra virgin", "cold pressed",
    "expeller pressed", "organic", "raw", "deodorized", "bleached",
    "hydrogenated", "fractionated", "stabilized", "pasteurized",
    "essential", "fragrance", "carrier", "high oleic", "low linoleic",
}

_PAREN_RE = re.compile(r"\s*\([^)]+\)\s*")
_SPACE_RE = re.compile(r"\s+")
_PERCENTAGE_RE = re.compile(r"\s+(\d+(?:\.\d+)?%)")


def _sha_key(*parts: str) -> str:
    joined = "|".join([str(p).strip() for p in parts if p is not None])
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


def _normalize_term(term: str) -> str:
    """Normalize a term for consistent clustering.
    
    Title-case for proper noun treatment, consistent with item_parser output.
    """
    t = (term or "").strip()
    if not t:
        return ""
    words = t.split()
    result = []
    for w in words:
        if w.isupper() and len(w) > 2:
            result.append(w.title())
        else:
            result.append(w)
    return " ".join(result)


def _parse_seed_name(raw_name: str, physical_form_explicit: str = "") -> tuple[str, str, str]:
    """Parse a seed item name into (term, variation, physical_form).
    
    Seed names are maker-friendly:
    - "Shea Butter" -> ("Shea", "", "Butter")
    - "Olive Oil (Extra Virgin)" -> ("Olive", "Extra Virgin", "Oil")
    - "Bread Flour" -> ("Flour", "Bread", "Powder")  # Flour is a derivative ingredient
    - "Apple Cider Vinegar" -> ("Vinegar", "Apple Cider", "Liquid")  # Vinegar is a derivative
    - "Salicylic Acid 2% Solution" -> ("Salicylic Acid", "2%", "Solution")
    - "Citric Acid" -> ("Citric Acid", "", "")  # Keep chemical names intact
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
    
    if tokens and tokens[-1].lower() in _DERIVATIVE_INGREDIENTS:
        derivative_key = tokens[-1].lower()
        derivative_info = _DERIVATIVE_INGREDIENTS[derivative_key]
        term = derivative_info["term"]
        if not physical_form:
            physical_form = derivative_info["physical_form"]
        if len(tokens) > 1:
            variation = " ".join(tokens[:-1])
        return term, variation, physical_form
    
    if tokens and tokens[-1].lower() in _FORM_TOKENS:
        if not physical_form:
            physical_form = tokens[-1]
        tokens = tokens[:-1]
    
    term = " ".join(tokens).strip()
    
    if not term:
        term = name
    
    term = _normalize_term(term)
    
    return term, variation, physical_form


def _extract_specs(item: dict[str, Any]) -> dict[str, Any]:
    specs = {}
    for field in SPEC_FIELDS:
        if field in item and item[field] is not None:
            specs[field] = item[field]
    return specs


def ingest_seed_items(dry_run: bool = False) -> tuple[int, int]:
    """Ingest seed items into compiler_state.db.
    
    Returns:
        (inserted_source_items, inserted_normalized_terms)
    """
    if not SEED_CATEGORIES_DIR.exists():
        print(f"Seed directory not found: {SEED_CATEGORIES_DIR}")
        return 0, 0

    database_manager.ensure_tables_exist()
    
    source_rows: list[dict[str, Any]] = []
    normalized_terms: dict[str, dict[str, Any]] = {}
    
    json_files = sorted(SEED_CATEGORIES_DIR.glob("*.json"))
    print(f"Found {len(json_files)} seed JSON files")

    for json_path in json_files:
        try:
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Failed to parse {json_path}: {e}")
            continue

        category_name = data.get("category_name", json_path.stem)
        items = data.get("items", [])

        for idx, item in enumerate(items):
            raw_name = (item.get("name") or "").strip()
            if not raw_name:
                continue

            inci_name = (item.get("inci_name") or "").strip()
            physical_form_explicit = (item.get("physical_form") or "").strip()
            specs = _extract_specs(item)

            definition, variation, physical_form = _parse_seed_name(raw_name, physical_form_explicit)
            
            origin = infer_origin(raw_name)
            ingredient_category = infer_primary_category(definition, origin, raw_name=raw_name) if definition else category_name
            refinement_level = infer_refinement(definition or raw_name, raw_name)
            derived_part = extract_plant_part(raw_name)

            status = "linked" if definition else "orphan"
            reason = None
            if not definition:
                reason = "Unable to derive definition term from seed item name"

            source_row_id = f"seed:{json_path.stem}:{idx}"
            key = _sha_key("seed", source_row_id, raw_name)
            content_hash = _sha_key("seed", raw_name, inci_name or "")

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
                "specs": specs,
            }

            source_rows.append({
                "key": key,
                "source": "seed",
                "source_row_id": source_row_id,
                "source_row_number": idx,
                "source_ref": json_path.name,
                "content_hash": content_hash,
                "is_composite": False,
                "raw_name": raw_name,
                "inci_name": inci_name or None,
                "cas_number": None,
                "cas_numbers_json": "[]",
                "derived_term": definition or None,
                "derived_variation": variation or None,
                "derived_physical_form": physical_form or None,
                "derived_part": derived_part or None,
                "derived_part_reason": "token_in_raw_name" if derived_part else None,
                "origin": origin or "Plant-Derived",
                "ingredient_category": ingredient_category or category_name,
                "refinement_level": refinement_level or None,
                "status": status,
                "needs_review_reason": reason,
                "derived_specs_json": json.dumps(specs, ensure_ascii=False) if specs else "{}",
                "derived_specs_sources_json": json.dumps({"seed": json_path.name}, ensure_ascii=False) if specs else "{}",
                "derived_specs_notes_json": "[]",
                "payload_json": json.dumps(payload, ensure_ascii=False),
            })

            if definition:
                rec = normalized_terms.setdefault(
                    definition,
                    {
                        "term": definition,
                        "seed_category": category_name,
                        "botanical_name": "",
                        "inci_name": inci_name or "",
                        "cas_number": "",
                        "description": "",
                        "ingredient_category": ingredient_category or category_name,
                        "origin": origin or "Plant-Derived",
                        "refinement_level": refinement_level,
                        "derived_from": "",
                        "ingredient_category_confidence": 80,
                        "origin_confidence": 80,
                        "refinement_confidence": 80,
                        "derived_from_confidence": 0,
                        "overall_confidence": 80,
                        "sources_json": json.dumps({"sources": ["seed"]}, ensure_ascii=False),
                    },
                )
                if inci_name and not rec.get("inci_name"):
                    rec["inci_name"] = inci_name

    if dry_run:
        print(f"\n[DRY RUN] Would insert {len(source_rows)} source items")
        for row in source_rows[:20]:
            print(f"  {row['raw_name']!r:45} => term={row['derived_term']!r:25}, var={row['derived_variation']!r:15}, form={row['derived_physical_form']!r}")
        print(f"\nNormalized terms: {len(normalized_terms)}")
        return len(source_rows), len(normalized_terms)

    existing = database_manager.delete_source_items_by_source("seed")
    print(f"Deleted {existing} existing seed source items")

    inserted_items = database_manager.upsert_source_items(source_rows)
    inserted_terms = database_manager.upsert_normalized_terms(list(normalized_terms.values()))
    
    print(f"Inserted {inserted_items} seed source items, {inserted_terms} normalized terms")
    return inserted_items, inserted_terms


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Ingest seed items into compiler_state.db")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    args = parser.parse_args()
    
    items, terms = ingest_seed_items(dry_run=args.dry_run)
    print(f"\nResult: {items} items, {terms} terms")


if __name__ == "__main__":
    main()
