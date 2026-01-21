"""Clean up garbage spec values in merged_item_forms and compiled_cluster_items.

This script fixes data quality issues from malformed TGSC source data where
multiple fields got concatenated together during scraping.

Garbage patterns to clean:
- safety_notes: "Information:" -> remove (empty placeholder)
- solubility: "... Organoleptic Properties: ..." -> extract just solubility part
- odor_description: "and/or flavor descriptions from others (if found)" -> remove
- flavor_description: "descriptions from others (if found)" -> remove
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from pathlib import Path

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "output" / "Final DB.db"

GARBAGE_PATTERNS = {
    "safety_notes": [
        r"^Information:?\s*$",
    ],
    "odor_description": [
        r"^and/or flavor descriptions from others.*$",
        r"^descriptions from others.*$",
    ],
    "flavor_description": [
        r"^descriptions from others.*$",
        r"^s, cosmetics.*$",
    ],
    "solubility": [
        r"\s*Organoleptic Properties:.*$",
        r"\s*Insoluble in:.*Organoleptic.*$",
    ],
}


def clean_spec_value(key: str, value) -> str | list | None:
    """Clean a spec value, returning None if it should be removed entirely."""
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item = clean_spec_value(key, item)
            if cleaned_item is not None:
                cleaned_list.append(cleaned_item)
        if not cleaned_list:
            return None
        if len(cleaned_list) == 1:
            return cleaned_list[0]
        return cleaned_list
    
    if not isinstance(value, str):
        return value
    
    cleaned = value.strip()
    if not cleaned:
        return None
    
    patterns = GARBAGE_PATTERNS.get(key, [])
    for pattern in patterns:
        if re.match(pattern, cleaned, re.IGNORECASE):
            return None
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    
    if key == "solubility" and cleaned:
        cleaned = re.sub(r"\s*Organoleptic Properties:.*", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s*Insoluble in:\s*\w+\s*Organoleptic.*", "", cleaned, flags=re.IGNORECASE).strip()
        if "Organoleptic" in cleaned or "descriptions from others" in cleaned:
            return None
    
    if key == "safety_notes" and cleaned:
        if cleaned.lower() in ("information:", "of our facilities and collaborators"):
            return None
    
    if key == "flavor_description" and cleaned:
        garbage_phrases = ["and fragrance", "& fragrance", "s and fragrance", "and food"]
        if cleaned.lower().strip() in [p.lower() for p in garbage_phrases]:
            return None
        for phrase in garbage_phrases:
            if cleaned.lower().startswith(phrase.lower()):
                return None
    
    return cleaned if cleaned else None


def clean_specs_dict(specs: dict) -> tuple[dict, int]:
    """Clean a specs dictionary, returning (cleaned_dict, changes_count)."""
    if not isinstance(specs, dict):
        return specs, 0
    
    cleaned = {}
    changes = 0
    
    for key, value in specs.items():
        if key in GARBAGE_PATTERNS:
            new_value = clean_spec_value(key, value)
            if new_value != value:
                changes += 1
                if new_value is not None:
                    cleaned[key] = new_value
            else:
                cleaned[key] = value
        else:
            cleaned[key] = value
    
    return cleaned, changes


def clean_merged_item_forms(conn: sqlite3.Connection, dry_run: bool = True) -> dict:
    """Clean merged_specs_json in merged_item_forms table."""
    cur = conn.cursor()
    cur.execute("SELECT id, merged_specs_json FROM merged_item_forms")
    
    updates = []
    total_changes = 0
    
    for row in cur.fetchall():
        item_id, specs_json = row
        if not specs_json:
            continue
        
        try:
            specs = json.loads(specs_json)
        except json.JSONDecodeError:
            continue
        
        cleaned, changes = clean_specs_dict(specs)
        if changes > 0:
            total_changes += changes
            updates.append((json.dumps(cleaned, ensure_ascii=False, sort_keys=True), item_id))
    
    if not dry_run and updates:
        cur.executemany(
            "UPDATE merged_item_forms SET merged_specs_json = ? WHERE id = ?",
            updates
        )
        conn.commit()
    
    return {"items_updated": len(updates), "fields_cleaned": total_changes, "dry_run": dry_run}


def clean_compiled_cluster_items(conn: sqlite3.Connection, dry_run: bool = True) -> dict:
    """Clean item_json specifications in compiled_cluster_items table."""
    cur = conn.cursor()
    cur.execute("SELECT cluster_id, merged_item_form_id, item_json FROM compiled_cluster_items WHERE item_json IS NOT NULL AND item_json != '{}'")
    
    updates = []
    total_changes = 0
    
    for row in cur.fetchall():
        cluster_id, mif_id, item_json = row
        if not item_json:
            continue
        
        try:
            item = json.loads(item_json)
        except json.JSONDecodeError:
            continue
        
        specs = item.get("specifications", {})
        if not isinstance(specs, dict):
            continue
        
        cleaned_specs, changes = clean_specs_dict(specs)
        if changes > 0:
            total_changes += changes
            item["specifications"] = cleaned_specs
            updates.append((json.dumps(item, ensure_ascii=False, sort_keys=True), cluster_id, mif_id))
    
    if not dry_run and updates:
        cur.executemany(
            "UPDATE compiled_cluster_items SET item_json = ? WHERE cluster_id = ? AND merged_item_form_id = ?",
            updates
        )
        conn.commit()
    
    return {"items_updated": len(updates), "fields_cleaned": total_changes, "dry_run": dry_run}


def run_cleanup(dry_run: bool = True) -> dict:
    """Run the full cleanup process."""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        merged_result = clean_merged_item_forms(conn, dry_run=dry_run)
        compiled_result = clean_compiled_cluster_items(conn, dry_run=dry_run)
        
        return {
            "merged_item_forms": merged_result,
            "compiled_cluster_items": compiled_result,
        }
    finally:
        conn.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Clean garbage spec values from database")
    p.add_argument("--dry-run", action="store_true", default=True, help="Show what would be cleaned without making changes")
    p.add_argument("--apply", action="store_true", help="Actually apply the changes")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    
    dry_run = not args.apply
    
    if dry_run:
        LOGGER.info("DRY RUN - no changes will be made")
    else:
        LOGGER.info("APPLYING changes to database")
    
    result = run_cleanup(dry_run=dry_run)
    
    LOGGER.info("Cleanup results:")
    LOGGER.info("  merged_item_forms: %s", result["merged_item_forms"])
    LOGGER.info("  compiled_cluster_items: %s", result["compiled_cluster_items"])
    
    if dry_run:
        LOGGER.info("Run with --apply to make changes permanent")


if __name__ == "__main__":
    main()
