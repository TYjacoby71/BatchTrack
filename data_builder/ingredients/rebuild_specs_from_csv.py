"""Rebuild merged_specs_json by re-extracting data from original TGSC CSV.

The original ingestion had parsing issues where TGSC scraped data had
concatenated fields. This script reads the raw CSV and properly extracts
specs for each item, then updates merged_item_forms.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "output" / "Final DB.db"
TGSC_CSV_PATH = BASE_DIR / "data_sources" / "tgsc_ingredients.csv"

SPEC_FIELDS = [
    "odor_description",
    "flavor_description",
    "solubility",
    "safety_notes",
    "boiling_point",
    "melting_point",
    "density",
    "molecular_weight",
    "molecular_formula",
]

DESCRIPTOR_FIELDS = [
    "category",
    "description",
    "uses",
    "synonyms",
    "natural_occurrence",
    "botanical_name",
    "url",
]

IDENTIFIER_FIELDS = [
    "cas_number",
    "fema_number",
    "einecs_number",
]


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _is_garbage(value: str) -> bool:
    """Check if a value is garbage/placeholder text."""
    garbage_patterns = [
        r"^Information:?\s*$",
        r"descriptions from others",
        r"Organoleptic Properties",
        r"^\s*$",
        r"^Type:\s*$",
        r"of our facilities and collaborators",
        r"GoogleAnalyticsObject",
        r"i\[r\]=i\[r\]",
    ]
    for pattern in garbage_patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def _parse_numeric(value: str, field: str) -> float | None:
    """Parse a numeric value from a string."""
    if not value:
        return None
    match = re.search(r"([\d.]+)", value)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def extract_specs_from_row(row: dict) -> dict[str, Any]:
    """Extract clean specs from a TGSC CSV row."""
    specs = {}
    
    for field in SPEC_FIELDS:
        value = _clean(row.get(field, ""))
        if not value or _is_garbage(value):
            continue
        
        if field in ("boiling_point", "melting_point", "density", "molecular_weight"):
            numeric = _parse_numeric(value, field)
            if numeric is not None:
                if field == "boiling_point":
                    specs["boiling_point_c"] = numeric
                    specs["boiling_point_text"] = value
                elif field == "melting_point":
                    specs["melting_point_c"] = numeric
                    specs["melting_point_text"] = value
                elif field == "density":
                    specs["density"] = numeric
                elif field == "molecular_weight":
                    specs["molecular_weight"] = numeric
                    specs["molecular_weight_text"] = value
        else:
            if field == "solubility":
                clean_sol = re.sub(r"\s*Organoleptic.*$", "", value, flags=re.IGNORECASE).strip()
                clean_sol = re.sub(r"\s*Insoluble in:.*Organoleptic.*$", "", clean_sol, flags=re.IGNORECASE).strip()
                if clean_sol and not _is_garbage(clean_sol):
                    specs["solubility"] = clean_sol
            else:
                specs[field] = value
    
    return specs


def _is_descriptor_garbage(value: str, field: str) -> bool:
    """Check if a descriptor value is garbage from bad scraping."""
    garbage_indicators = [
        r"GoogleAnalyticsObject",
        r"i\[r\]=i\[r\]",
        r"function\s*\(",
        r"Supplier Sponsors",
        r"Articles Notes",
        r"Information:\s*$",
        r"self-gelation",
        r"^\s*\(i,s,o,g,r,a,m\)",
        r"TERPENA S$",
        r"Nikkaji Web:",
        r"FDA UNII:",
        r"CAS Number:",
        r"3D/inchi",
        r"Organoleptic Properties",
        r"^\s*ring\s",
        r"^\s*d in conjunction",
    ]
    for pattern in garbage_indicators:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    if len(value) < 3:
        return True
    return False


def extract_descriptors_from_row(row: dict) -> dict[str, Any]:
    """Extract descriptors (category, description, uses, synonyms, etc.) from a TGSC CSV row."""
    descriptors = {}
    
    for field in DESCRIPTOR_FIELDS:
        value = _clean(row.get(field, ""))
        if not value or _is_garbage(value) or _is_descriptor_garbage(value, field):
            continue
        
        if field == "synonyms":
            syns = [s.strip() for s in value.split(";") if s.strip() and len(s.strip()) > 2 and not _is_descriptor_garbage(s.strip(), "synonyms")]
            syns = [s for s in syns if not any(g in s.lower() for g in ["articles", "supplier", "sponsors", "notes"])]
            if syns:
                descriptors["synonyms"] = syns
        elif field == "natural_occurrence":
            occurrences = [o.strip() for o in value.split(",") if o.strip() and len(o.strip()) > 2 and not _is_descriptor_garbage(o.strip(), "natural_occurrence")]
            occurrences = [o for o in occurrences if not any(g in o.lower() for g in ["synonyms", "articles", "self-gelation", "ring "])]
            if occurrences:
                descriptors["natural_occurrence"] = occurrences
        elif field in ("description", "uses"):
            if not _is_descriptor_garbage(value, field) and len(value) > 10:
                descriptors[field] = value
        else:
            descriptors[field] = value
    
    return descriptors


def extract_identifiers_from_row(row: dict) -> dict[str, Any]:
    """Extract identifiers (CAS, FEMA, EINECS) from a TGSC CSV row."""
    identifiers = {}
    
    for field in IDENTIFIER_FIELDS:
        value = _clean(row.get(field, ""))
        if not value or value.lower() in ("none", "n/a", ""):
            continue
        identifiers[field] = value
    
    return identifiers


def build_tgsc_lookup() -> dict[str, dict[str, Any]]:
    """Build a lookup from common_name to all extractable data from TGSC CSV."""
    if not TGSC_CSV_PATH.exists():
        LOGGER.warning("TGSC CSV not found: %s", TGSC_CSV_PATH)
        return {}
    
    lookup = {}
    with TGSC_CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = _clean(row.get("common_name", ""))
            if not name:
                continue
            name_key = name.lower().strip()
            
            specs = extract_specs_from_row(row)
            descriptors = extract_descriptors_from_row(row)
            identifiers = extract_identifiers_from_row(row)
            
            if specs or descriptors or identifiers:
                lookup[name_key] = {
                    "specs": specs,
                    "descriptors": descriptors,
                    "identifiers": identifiers,
                }
    
    LOGGER.info("Built TGSC lookup with %d entries", len(lookup))
    return lookup


def rebuild_merged_data(dry_run: bool = True) -> dict:
    """Rebuild merged_specs_json and merged_descriptors_json from TGSC CSV data."""
    tgsc_lookup = build_tgsc_lookup()
    if not tgsc_lookup:
        return {"error": "No TGSC data available"}
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT mif.id, mif.derived_term, mif.merged_specs_json, mif.merged_descriptors_json, mif.has_tgsc,
               GROUP_CONCAT(si.raw_name, '|||') as raw_names
        FROM merged_item_forms mif
        LEFT JOIN source_items si ON si.merged_item_id = mif.id AND si.source = 'tgsc'
        WHERE mif.has_tgsc = 1
        GROUP BY mif.id
    """)
    
    spec_updates = []
    desc_updates = []
    matched = 0
    specs_enriched = 0
    descs_enriched = 0
    
    for row in cur.fetchall():
        mif_id, derived_term, current_specs_json, current_desc_json, has_tgsc, raw_names_str = row
        
        tgsc_data = None
        
        if raw_names_str:
            for raw_name in raw_names_str.split("|||"):
                name_key = _clean(raw_name).lower()
                if name_key in tgsc_lookup:
                    tgsc_data = tgsc_lookup[name_key]
                    break
        
        if not tgsc_data:
            term_key = _clean(derived_term).lower()
            if term_key in tgsc_lookup:
                tgsc_data = tgsc_lookup[term_key]
        
        if not tgsc_data:
            continue
        
        matched += 1
        
        try:
            current_specs = json.loads(current_specs_json) if current_specs_json else {}
        except json.JSONDecodeError:
            current_specs = {}
        
        try:
            current_desc = json.loads(current_desc_json) if current_desc_json else {}
        except json.JSONDecodeError:
            current_desc = {}
        
        merged_specs = dict(current_specs)
        merged_desc = dict(current_desc)
        spec_changes = 0
        desc_changes = 0
        
        tgsc_specs = tgsc_data.get("specs", {})
        tgsc_descs = tgsc_data.get("descriptors", {})
        tgsc_ids = tgsc_data.get("identifiers", {})
        
        for key, value in tgsc_specs.items():
            if key not in merged_specs or merged_specs[key] in (None, "", [], {}):
                merged_specs[key] = value
                spec_changes += 1
            elif _is_garbage(str(merged_specs.get(key, ""))):
                merged_specs[key] = value
                spec_changes += 1
        
        for key, value in tgsc_ids.items():
            if key not in merged_specs or merged_specs[key] in (None, "", [], {}):
                merged_specs[key] = value
                spec_changes += 1
        
        for key, value in tgsc_descs.items():
            if key not in merged_desc or merged_desc[key] in (None, "", [], {}):
                merged_desc[key] = value
                desc_changes += 1
            elif _is_garbage(str(merged_desc.get(key, ""))):
                merged_desc[key] = value
                desc_changes += 1
        
        if spec_changes > 0:
            specs_enriched += 1
            spec_updates.append((json.dumps(merged_specs, ensure_ascii=False, sort_keys=True), mif_id))
        
        if desc_changes > 0:
            descs_enriched += 1
            desc_updates.append((json.dumps(merged_desc, ensure_ascii=False, sort_keys=True), mif_id))
    
    if not dry_run:
        if spec_updates:
            cur.executemany(
                "UPDATE merged_item_forms SET merged_specs_json = ? WHERE id = ?",
                spec_updates
            )
        if desc_updates:
            cur.executemany(
                "UPDATE merged_item_forms SET merged_descriptors_json = ? WHERE id = ?",
                desc_updates
            )
        conn.commit()
    
    conn.close()
    
    return {
        "tgsc_items_matched": matched,
        "specs_enriched": specs_enriched,
        "descriptors_enriched": descs_enriched,
        "spec_updates_applied": len(spec_updates) if not dry_run else 0,
        "desc_updates_applied": len(desc_updates) if not dry_run else 0,
        "dry_run": dry_run,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Rebuild specs from TGSC CSV")
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--apply", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    
    dry_run = not args.apply
    
    if dry_run:
        LOGGER.info("DRY RUN - no changes will be made")
    else:
        LOGGER.info("APPLYING changes to database")
    
    result = rebuild_merged_data(dry_run=dry_run)
    LOGGER.info("Rebuild results: %s", result)
    
    if dry_run:
        LOGGER.info("Run with --apply to make changes permanent")


if __name__ == "__main__":
    main()
