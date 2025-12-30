"""Normalize ingredient sources (item-first).

This is the ONLY supported "normalizer" behavior now:
- Read CosIng (INCI) + TGSC CSVs
- Treat each row as a *source item* (not a base term)
- Derive and dedupe *definition terms* from those items
- Persist results into compiler_state.db:
  - source_items (item-first records; includes orphan/review status)
  - normalized_terms (deduped derived definition terms)

Outputs:
- Writes a lightweight `output/normalized_terms.csv` export for inspection.
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Any, Dict, List

from . import database_manager
from .ingest_source_items import ingest_sources

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_SOURCES_DIR = BASE_DIR / "data_sources"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_CSV = OUTPUT_DIR / "normalized_terms.csv"


def _write_normalized_terms_csv(path: Path) -> int:
    """Export normalized_terms table to CSV; returns row count."""
    database_manager.ensure_tables_exist()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with database_manager.get_session() as session:
        rows = session.query(database_manager.NormalizedTerm).order_by(database_manager.NormalizedTerm.term.asc()).all()

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
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "term": r.term,
                    "seed_category": r.seed_category or "",
                    "ingredient_category": r.ingredient_category or "",
                    "origin": r.origin or "",
                    "refinement_level": r.refinement_level or "",
                    "derived_from": r.derived_from or "",
                    "ingredient_category_confidence": r.ingredient_category_confidence or "",
                    "origin_confidence": r.origin_confidence or "",
                    "refinement_confidence": r.refinement_confidence or "",
                    "derived_from_confidence": r.derived_from_confidence or "",
                    "overall_confidence": r.overall_confidence or "",
                    "botanical_name": r.botanical_name or "",
                    "inci_name": r.inci_name or "",
                    "cas_number": r.cas_number or "",
                    "description": r.description or "",
                }
            )

    return len(rows)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize INCI/TGSC sources (item-first)")
    parser.add_argument("--tgsc", default=str(DATA_SOURCES_DIR / "tgsc_ingredients.csv"))
    parser.add_argument("--cosing", default=str(DATA_SOURCES_DIR / "cosing.csv"))
    parser.add_argument("--out", default=str(OUTPUT_CSV))
    parser.add_argument("--limit", type=int, default=0, help="Optional cap (combined across sources)")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)

    tgsc_path = Path(args.tgsc).resolve()
    cosing_path = Path(args.cosing).resolve()
    out_path = Path(args.out).resolve()
    limit = int(args.limit) if args.limit else None

    inserted_items, inserted_terms = ingest_sources(
        cosing_path=cosing_path,
        tgsc_path=tgsc_path,
        limit=limit,
    )
    LOGGER.info("Ingested source_items (new=%s) and normalized_terms (new=%s)", inserted_items, inserted_terms)

    exported = _write_normalized_terms_csv(out_path)
    LOGGER.info("Wrote %s normalized terms to %s", exported, out_path)

    summary = database_manager.get_source_item_summary()
    LOGGER.info("source_items summary: %s", summary)


if __name__ == "__main__":
    main()

