"""Normalize ingredient sources into definition TERMS (not items).

This is the "terms normalizer":
- Read CosIng (INCI) + TGSC CSVs
- Derive a canonical *definition term* from each source row (conservative)
- De-duplicate into a unique set of definition terms
- Best-effort infer origin/category/refinement for the definition
- Upsert into compiler_state.db (normalized_terms table)
- Write output/normalized_terms.csv for inspection

Important:
- This module does NOT create item rows. Item ingestion is handled separately
  by `ingest_source_items.py` (kept as a distinct script by design).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import database_manager
from .item_parser import derive_definition_term, infer_origin, infer_primary_category, infer_refinement

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_SOURCES_DIR = BASE_DIR / "data_sources"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_CSV = OUTPUT_DIR / "normalized_terms.csv"


def _first_cas(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    return v.split(",")[0].strip()


def _iter_csv(path: Path) -> List[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def normalize_to_terms(*, cosing_path: Path, tgsc_path: Path, limit: Optional[int] = None) -> List[dict[str, Any]]:
    """Create normalized_terms rows (definition terms) from sources."""
    rows: dict[str, dict[str, Any]] = {}
    sources_by_term: dict[str, list[dict[str, Any]]] = {}

    def _register(source: str, raw_name: str, *, inci_name: str = "", cas_number: str = "", extra: dict[str, Any] | None = None) -> None:
        raw = (raw_name or "").strip()
        if not raw:
            return
        term = derive_definition_term(raw)
        if not term:
            return

        origin = infer_origin(raw)
        ingredient_category = infer_primary_category(term, origin)
        refinement_level = infer_refinement(term, raw)

        # Track sources (for inspection)
        sources_by_term.setdefault(term, []).append(
            {
                "source": source,
                "raw_name": raw,
                "inci_name": (inci_name or "").strip(),
                "cas_number": (cas_number or "").strip(),
            }
        )

        rec = rows.setdefault(
            term,
            {
                "term": term,
                # use ingredient_category as the cursor bucket by default (Stage-1 can override)
                "seed_category": ingredient_category or None,
                "botanical_name": "",
                "inci_name": "",
                "cas_number": "",
                "description": "",
                "ingredient_category": ingredient_category or None,
                "origin": origin or None,
                "refinement_level": refinement_level or None,
                "derived_from": "",
                "ingredient_category_confidence": 60,
                "origin_confidence": 60,
                "refinement_confidence": 60,
                "derived_from_confidence": 0,
                "overall_confidence": 60,
                "sources_json": "{}",
                "source_count": 0,
            },
        )
        # Best-effort: keep first-seen identity hints (do not overwrite)
        if (inci_name or "").strip() and not rec.get("inci_name"):
            rec["inci_name"] = (inci_name or "").strip()
        if (cas_number or "").strip() and not rec.get("cas_number"):
            rec["cas_number"] = (cas_number or "").strip()

    # CosIng (INCI)
    count = 0
    for row in _iter_csv(cosing_path):
        if limit and count >= int(limit):
            break
        inci = (row.get("INCI name") or row.get("INCI Name") or "").strip()
        if not inci:
            continue
        cas = _first_cas((row.get("CAS No") or "").strip())
        _register("cosing", inci, inci_name=inci, cas_number=cas, extra=row)
        count += 1

    # TGSC
    for row in _iter_csv(tgsc_path):
        if limit and count >= int(limit):
            break
        name = (row.get("common_name") or row.get("name") or "").strip()
        if not name:
            continue
        cas = _first_cas((row.get("cas_number") or "").strip())
        _register("tgsc", name, inci_name="", cas_number=cas, extra=row)
        count += 1

    out: List[dict[str, Any]] = []
    for term in sorted(rows.keys(), key=lambda s: (s.casefold(), s)):
        rec = rows[term]
        srcs = sources_by_term.get(term, [])
        rec["sources_json"] = json.dumps({"sources": srcs}, ensure_ascii=False, sort_keys=True)
        rec["source_count"] = len(srcs)
        out.append(rec)
    return out


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "term",
        "seed_category",
        "ingredient_category",
        "origin",
        "refinement_level",
        "derived_from",
        "ingredient_category_confidence",
        "origin_confidence",
        "refinement_confidence",
        "derived_from_confidence",
        "overall_confidence",
        "botanical_name",
        "inci_name",
        "cas_number",
        "description",
        "source_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") or "" for k in fieldnames})


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize INCI/TGSC sources into definition terms")
    parser.add_argument("--tgsc", default=str(DATA_SOURCES_DIR / "tgsc_ingredients.csv"))
    parser.add_argument("--cosing", default=str(DATA_SOURCES_DIR / "cosing.csv"))
    parser.add_argument("--out", default=str(OUTPUT_CSV))
    parser.add_argument("--limit", type=int, default=0, help="Optional cap (combined across sources)")
    parser.add_argument("--no-db", action="store_true", help="Do not upsert into compiler_state.db")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)

    tgsc_path = Path(args.tgsc).resolve()
    cosing_path = Path(args.cosing).resolve()
    out_path = Path(args.out).resolve()
    limit = int(args.limit) if args.limit else None

    term_rows = normalize_to_terms(cosing_path=cosing_path, tgsc_path=tgsc_path, limit=limit)
    LOGGER.info("Derived %s normalized definition terms from sources.", len(term_rows))
    write_csv(out_path, term_rows)
    LOGGER.info("Wrote normalized terms CSV to %s", out_path)

    if not args.no_db:
        inserted = database_manager.upsert_normalized_terms(term_rows)
        LOGGER.info("Upserted normalized_terms into DB (new=%s)", inserted)


if __name__ == "__main__":
    main()

