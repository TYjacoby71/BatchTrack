"""Direct seed ingestion into Final DB.db.

This script reads seed JSON files and inserts them directly into the Final DB.db
source_items and merged_item_forms tables, then links seed specs to merged items.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

FINAL_DB_PATH = Path(__file__).resolve().parent / "output" / "Final DB.db"
SEED_CATEGORIES_DIR = Path(__file__).resolve().parents[2] / "app" / "seeders" / "globallist" / "ingredients" / "categories"

_FORM_TOKENS = {
    "oil", "butter", "wax", "powder", "extract", "tincture", "hydrosol",
    "absolute", "concrete", "resin", "gum", "solution", "distillate",
    "concentrate", "flour", "granules", "flakes", "crystals", "chips",
    "shreds", "ribbons", "paste", "cream", "gel", "liquid", "solid",
    "clay", "glycerite",
}

_CHEMICAL_FORM_TOKENS = {"acid", "salt", "ester", "oxide", "hydroxide"}

_VARIATION_TOKENS = {
    "refined", "unrefined", "virgin", "extra virgin", "cold pressed",
    "expeller pressed", "organic", "raw", "deodorized", "bleached",
    "hydrogenated", "fractionated", "stabilized", "pasteurized",
    "essential", "fragrance", "carrier", "high oleic", "low linoleic",
}

_INLINE_VARIATION_TOKENS = {"essential", "fragrance", "carrier"}

_PAREN_RE = re.compile(r"\s*\([^)]+\)\s*")
_SPACE_RE = re.compile(r"\s+")

SPEC_FIELDS = {
    "saponification_value", "iodine_value", "melting_point_c", "flash_point_c",
    "fatty_acid_profile", "comedogenic_rating", "recommended_shelf_life_days",
    "density", "ph_range", "hlb_value", "solubility", "viscosity",
    "refractive_index", "specific_gravity", "acid_value", "peroxide_value",
    "unsaponifiable_matter",
}


def _sha_key(*parts: str) -> str:
    joined = "|".join([str(p).strip() for p in parts if p is not None])
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()


_PERCENTAGE_RE = re.compile(r"\s+(\d+(?:\.\d+)?%)")


def _parse_seed_name(raw_name: str, physical_form_explicit: str = "") -> tuple[str, str, str]:
    """Parse a seed item name into (term, variation, physical_form).
    
    For chemicals like "Salicylic Acid", we keep the full name as term.
    For "Salicylic Acid 2% Solution", term="Salicylic Acid", form="Solution".
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


def _extract_specs(item: dict[str, Any]) -> dict[str, Any]:
    specs = {}
    for field in SPEC_FIELDS:
        if field in item and item[field] is not None:
            specs[field] = item[field]
    return specs


def ingest_seeds_to_final_db(dry_run: bool = False) -> tuple[int, int]:
    """Ingest seed items directly into Final DB.db."""
    if not SEED_CATEGORIES_DIR.exists():
        print(f"Seed directory not found: {SEED_CATEGORIES_DIR}")
        return 0, 0

    conn = sqlite3.connect(FINAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    source_rows = []
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
            
            definition, variation, physical_form = _parse_seed_name(raw_name, physical_form_explicit)
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
                "source_ref": str(json_path.name),
                "content_hash": content_hash,
                "is_composite": 0,
                "definition_display_name": None,
                "item_display_name": raw_name,
                "derived_function_tags_json": "[]",
                "derived_function_tag_entries_json": "[]",
                "derived_master_categories_json": "[]",
                "derived_specs_json": json.dumps(specs) if specs else None,
                "derived_specs_sources_json": "{}",
                "derived_specs_notes_json": "[]",
                "merged_item_id": None,
                "variation_bypass": 0,
                "variation_bypass_reason": None,
                "definition_cluster_id": None,
                "definition_cluster_confidence": None,
                "definition_cluster_reason": None,
                "raw_name": raw_name,
                "inci_name": inci_name or None,
                "cas_number": None,
                "derived_term": definition or None,
                "derived_variation": variation or None,
                "derived_physical_form": physical_form or None,
                "derived_part": None,
                "derived_part_reason": None,
                "cas_numbers_json": "[]",
                "origin": "Plant-Derived",
                "ingredient_category": category_name,
                "refinement_level": None,
                "status": "linked" if definition else "orphan",
                "needs_review_reason": None,
                "payload_json": json.dumps(payload, ensure_ascii=False),
                "ingested_at": datetime.utcnow().isoformat(),
            })

    if dry_run:
        for row in source_rows[:15]:
            print(f"  {row['raw_name']!r:35} => term={row['derived_term']!r:20}, var={row['derived_variation']!r:15}, form={row['derived_physical_form']!r}")
        print(f"\n[DRY RUN] Would insert {len(source_rows)} source items")
        conn.close()
        return len(source_rows), 0

    cur.execute("DELETE FROM source_items WHERE source = 'seed'")
    deleted = cur.rowcount
    print(f"Deleted {deleted} existing seed source items")

    cols = list(source_rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join([f'"{c}"' for c in cols])
    insert_sql = f"INSERT INTO source_items ({col_names}) VALUES ({placeholders})"

    for row in source_rows:
        vals = [row[c] for c in cols]
        cur.execute(insert_sql, vals)

    conn.commit()
    print(f"Inserted {len(source_rows)} seed source items")

    linked = link_seed_specs_to_merged_items(cur)
    conn.commit()
    conn.close()

    return len(source_rows), linked


def link_seed_specs_to_merged_items(cur: sqlite3.Cursor) -> int:
    """Link seed specs to matching merged_item_forms by term.
    
    Uses a tiered matching approach:
    1. Exact term match (case insensitive)
    2. Term starts-with match for partial matches
    3. Term contains match as fallback
    """
    cur.execute("""
        SELECT key, derived_term, derived_variation, derived_physical_form, derived_specs_json
        FROM source_items WHERE source = 'seed' AND derived_specs_json IS NOT NULL
    """)
    seed_items = cur.fetchall()
    
    linked = 0
    for seed in seed_items:
        term = (seed[1] or "").strip()
        var = (seed[2] or "").strip().lower()
        form = (seed[3] or "").strip().lower()
        specs = seed[4]
        
        if not term or not specs:
            continue

        term_lower = term.lower()
        
        cur.execute("""
            SELECT id FROM merged_item_forms 
            WHERE LOWER(derived_term) = ?
            ORDER BY 
                CASE WHEN LOWER(derived_physical_form) = ? THEN 0 ELSE 1 END,
                CASE WHEN LOWER(derived_variation) = ? THEN 0 ELSE 1 END
            LIMIT 1
        """, (term_lower, form, var))
        
        match = cur.fetchone()
        
        if not match:
            cur.execute("""
                SELECT id FROM merged_item_forms 
                WHERE LOWER(derived_term) LIKE ?
                ORDER BY LENGTH(derived_term),
                    CASE WHEN LOWER(derived_physical_form) = ? THEN 0 ELSE 1 END
                LIMIT 1
            """, (f"{term_lower}%", form))
            match = cur.fetchone()
        
        if not match:
            cur.execute("""
                SELECT id FROM merged_item_forms 
                WHERE LOWER(derived_term) LIKE ?
                ORDER BY LENGTH(derived_term),
                    CASE WHEN LOWER(derived_physical_form) = ? THEN 0 ELSE 1 END
                LIMIT 1
            """, (f"%{term_lower}%", form))
            match = cur.fetchone()
        
        if match:
            cur.execute("""
                UPDATE merged_item_forms SET app_seed_specs_json = ? WHERE id = ?
            """, (specs, match[0]))
            linked += 1
            print(f"  Linked specs for '{term}' -> merged_item_form #{match[0]}")
    
    print(f"Linked {linked} seed specs to merged items")
    return linked


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest seed items into Final DB.db")
    parser.add_argument("--dry-run", action="store_true", help="Don't write, just show what would happen")
    args = parser.parse_args()
    
    inserted, linked = ingest_seeds_to_final_db(dry_run=args.dry_run)
    print(f"\nResult: {inserted} items inserted, {linked} specs linked")


if __name__ == "__main__":
    main()
