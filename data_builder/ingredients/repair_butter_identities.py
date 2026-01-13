#!/usr/bin/env python3
"""Repair pass: fix butter identity shape in an existing DB (no full re-ingest).

Why:
- Older parsing treated "butter" as BOTH variation + physical_form ("Butter", "Butter").
- Desired model: "Butter" is a physical_form; variation should be "" (or something like Refined/Unrefined).

What this script does:
- Updates `source_items` rows where derived_variation == 'Butter' and derived_physical_form == 'Butter'
  -> derived_variation = '' (keeps physical_form as Butter).
- Updates `merged_item_forms` similarly.
- Optionally consolidates duplicate merged_item_forms identities created by the normalization
  (limited to the affected term+form combos), while preserving merged_specs_json (fill-only) and PubChem
  content stored inside merged_specs_json.

This is designed to be safe to run AFTER PubChem Stage 3 apply:
- We do NOT wipe specs; we keep merged_specs_json and merge fill-only when consolidating.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from sqlalchemy import or_

from . import database_manager

LOGGER = logging.getLogger(__name__)


def _safe_json(text: Any, default: Any) -> Any:
    try:
        return json.loads(text) if isinstance(text, str) and text.strip() else default
    except Exception:
        return default


def _merge_fill_only(base: Any, patch: Any) -> Any:
    """Fill-only merge for dict/list primitives (preserve base where non-empty)."""
    if isinstance(base, dict) and isinstance(patch, dict):
        out = dict(base)
        for k, v in patch.items():
            if k in out and out.get(k) not in (None, "", [], {}, "unknown"):
                continue
            if v in (None, "", [], {}, "unknown"):
                continue
            out[k] = v
        return out
    if isinstance(base, list) and isinstance(patch, list):
        if not base:
            return patch
        return base
    return base if base not in (None, "", "unknown") else patch


def _merge_json_fill_only(a: str | None, b: str | None) -> str:
    aa = _safe_json(a, {})
    bb = _safe_json(b, {})
    merged = _merge_fill_only(aa, bb)
    return json.dumps(merged if isinstance(merged, dict) else {}, ensure_ascii=False, sort_keys=True)


def repair(*, consolidate: bool, dry_run: bool) -> dict[str, int]:
    database_manager.ensure_tables_exist()
    stats = {
        "source_items_fixed": 0,
        "source_items_bypass_updated": 0,
        "source_items_dairy_butter_normalized": 0,
        "merged_item_forms_fixed": 0,
        "merged_item_forms_consolidated": 0,
    }

    with database_manager.get_session() as session:
        # 1) Fix source_items identity fields (form-only tokens mistakenly stored as variations).
        form_only_tokens = {"Butter", "Wax", "Resin", "Gum", "Gel", "Paste", "Hydrosol", "Oil", "Powder"}
        src_rows = (
            session.query(database_manager.SourceItem)
            .filter(
                database_manager.SourceItem.derived_variation.in_(list(form_only_tokens)),
                database_manager.SourceItem.derived_variation == database_manager.SourceItem.derived_physical_form,
            )
            .all()
        )
        for r in src_rows:
            if not dry_run:
                r.derived_variation = ""
            stats["source_items_fixed"] += 1

        # Normalize dairy butter: ensure it's treated as an Animal/Dairy base term.
        # We use a conservative matcher (raw_name / inci_name equals butter family, or well-known CAS).
        dairy_candidates = (
            session.query(database_manager.SourceItem)
            .filter(
                or_(
                    database_manager.func.lower(database_manager.func.trim(database_manager.SourceItem.raw_name)).in_(
                        ["butter", "salted butter", "unsalted butter"]
                    ),
                    database_manager.func.lower(database_manager.func.trim(database_manager.SourceItem.inci_name)).in_(["butter"]),
                    database_manager.SourceItem.cas_number == "8029-34-3",
                )
            )
            .all()
        )
        for r in dairy_candidates:
            raw = (getattr(r, "raw_name", "") or "").strip().lower().strip(" ,")
            inci = (getattr(r, "inci_name", "") or "").strip().lower().strip(" ,")
            cas = (getattr(r, "cas_number", "") or "").strip()
            if raw not in {"butter", "salted butter", "unsalted butter"} and inci not in {"butter"} and cas != "8029-34-3":
                continue
            # Force base term + animal/dairy classification.
            new_var = ""
            if "unsalted" in raw:
                new_var = "Unsalted"
            elif "salted" in raw:
                new_var = "Salted"
            if not dry_run:
                r.derived_term = "Butter"
                r.derived_physical_form = "Butter"
                r.derived_variation = new_var
                r.origin = "Animal-Derived"
                r.ingredient_category = "Animal - Dairy"
            stats["source_items_dairy_butter_normalized"] += 1

        # Ensure variation_bypass is set for plant-derived form-only rows with no variation.
        plant_butter = (
            session.query(database_manager.SourceItem)
            .filter(
                database_manager.SourceItem.derived_physical_form.in_(list(form_only_tokens)),
                database_manager.SourceItem.derived_variation.in_(("", None)),
                database_manager.SourceItem.origin == "Plant-Derived",
            )
            .all()
        )
        for r in plant_butter:
            old = int(getattr(r, "variation_bypass", 0) or 0)
            if old != 1:
                if not dry_run:
                    r.variation_bypass = 1
                    r.variation_bypass_reason = "form_only"
                stats["source_items_bypass_updated"] += 1

        # 2) Fix merged_item_forms identity fields.
        mif_rows = (
            session.query(database_manager.MergedItemForm)
            .filter(
                database_manager.MergedItemForm.derived_variation.in_(list(form_only_tokens)),
                database_manager.MergedItemForm.derived_variation == database_manager.MergedItemForm.derived_physical_form,
            )
            .all()
        )
        affected_terms: set[str] = set()
        for r in mif_rows:
            affected_terms.add(str(r.derived_term))
            if not dry_run:
                r.derived_variation = ""
            stats["merged_item_forms_fixed"] += 1

        # 3) Consolidate duplicates created by normalization.
        # NOTE: this can create duplicates for ANY form-only token we normalize, not just Butter.
        if consolidate and affected_terms:
            for term in sorted(affected_terms):
                for form in sorted(form_only_tokens):
                    dupes = (
                        session.query(database_manager.MergedItemForm)
                        .filter(
                            database_manager.MergedItemForm.derived_term == term,
                            database_manager.MergedItemForm.derived_physical_form == form,
                            database_manager.MergedItemForm.derived_variation.in_(("", None)),
                        )
                        .order_by(database_manager.MergedItemForm.id.asc())
                        .all()
                    )
                    if len(dupes) <= 1:
                        continue

                    keep = dupes[0]
                    for d in dupes[1:]:
                        keep_keys = set(_safe_json(getattr(keep, "member_source_item_keys_json", "[]"), []))
                        drop_keys = set(_safe_json(getattr(d, "member_source_item_keys_json", "[]"), []))
                        merged_keys = sorted({k for k in (keep_keys | drop_keys) if k})

                        keep_cas = set(_safe_json(getattr(keep, "cas_numbers_json", "[]"), []))
                        drop_cas = set(_safe_json(getattr(d, "cas_numbers_json", "[]"), []))
                        merged_cas = sorted({c for c in (keep_cas | drop_cas) if c})

                        keep_parts = set(_safe_json(getattr(keep, "derived_parts_json", "[]"), []))
                        drop_parts = set(_safe_json(getattr(d, "derived_parts_json", "[]"), []))
                        merged_parts = sorted({p for p in (keep_parts | drop_parts) if p})

                        if not dry_run:
                            keep.member_source_item_keys_json = json.dumps(merged_keys, ensure_ascii=False, sort_keys=True)
                            keep.cas_numbers_json = json.dumps(merged_cas, ensure_ascii=False, sort_keys=True)
                            keep.derived_parts_json = json.dumps(merged_parts, ensure_ascii=False, sort_keys=True)
                            keep.source_row_count = int(getattr(keep, "source_row_count", 0) or 0) + int(getattr(d, "source_row_count", 0) or 0)
                            keep.has_cosing = bool(getattr(keep, "has_cosing", False) or getattr(d, "has_cosing", False))
                            keep.has_tgsc = bool(getattr(keep, "has_tgsc", False) or getattr(d, "has_tgsc", False))
                            keep.has_seed = bool(getattr(keep, "has_seed", False) or getattr(d, "has_seed", False))
                            keep.merged_specs_json = _merge_json_fill_only(getattr(keep, "merged_specs_json", "{}"), getattr(d, "merged_specs_json", "{}"))
                            keep.merged_specs_sources_json = _merge_json_fill_only(getattr(keep, "merged_specs_sources_json", "{}"), getattr(d, "merged_specs_sources_json", "{}"))
                            a_notes = _safe_json(getattr(keep, "merged_specs_notes_json", "[]"), [])
                            b_notes = _safe_json(getattr(d, "merged_specs_notes_json", "[]"), [])
                            if isinstance(a_notes, list) and isinstance(b_notes, list):
                                keep.merged_specs_notes_json = json.dumps(a_notes + [x for x in b_notes if x not in a_notes], ensure_ascii=False, sort_keys=True)

                            session.query(database_manager.SourceItem).filter(database_manager.SourceItem.merged_item_id == d.id).update({"merged_item_id": keep.id})
                            try:
                                session.execute(
                                    database_manager.text("UPDATE pubchem_item_matches SET merged_item_form_id = :to_id WHERE merged_item_form_id = :from_id"),
                                    {"to_id": keep.id, "from_id": d.id},
                                )
                            except Exception:
                                pass
                            session.delete(d)
                        stats["merged_item_forms_consolidated"] += 1

    return stats


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    p = argparse.ArgumentParser(description="Repair butter identity fields without re-ingesting")
    p.add_argument("--db-path", default="", help="SQLite DB path override (otherwise uses compiler_state.db)")
    p.add_argument("--dry-run", action="store_true", help="Compute and log changes without writing")
    p.add_argument("--no-consolidate", action="store_true", help="Do not consolidate duplicate merged_item_forms")
    args = p.parse_args()

    if (args.db_path or "").strip():
        database_manager.configure_db_path((args.db_path or "").strip())

    stats = repair(consolidate=(not bool(args.no_consolidate)), dry_run=bool(args.dry_run))
    LOGGER.info("repair complete (db=%s): %s", database_manager.DB_PATH, stats)


if __name__ == "__main__":
    main()

