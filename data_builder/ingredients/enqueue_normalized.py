"""Enqueue normalized base terms into the compiler task queue.

Supports:
- Seeding from normalized_terms table (preferred)
- Seeding from normalized_terms.csv (fallback/export use-case)
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

from . import database_manager

LOGGER = logging.getLogger(__name__)

# Centralized path layout (supports both module and direct script execution).
try:  # pragma: no cover
    from data_builder import paths as builder_paths  # type: ignore
except Exception:  # pragma: no cover
    builder_paths = None  # type: ignore

if builder_paths is not None:
    builder_paths.ensure_layout()
    DEFAULT_NORMALIZED_CSV = builder_paths.NORMALIZED_TERMS_CSV
else:
    DEFAULT_NORMALIZED_CSV = Path(__file__).resolve().parents[1] / "outputs" / "normalized_terms.csv"


def _seed_from_db(limit: int | None) -> int:
    database_manager.ensure_tables_exist()
    inserted = 0
    with database_manager.get_session() as session:
        q = session.query(database_manager.NormalizedTerm).order_by(database_manager.NormalizedTerm.term.asc())
        if limit:
            q = q.limit(int(limit))
        rows = q.all()
        for r in rows:
            if database_manager.upsert_term(r.term, database_manager.DEFAULT_PRIORITY, seed_category=r.seed_category):
                inserted += 1
    return inserted


def _seed_from_csv(path: Path, limit: int | None) -> int:
    inserted = 0
    database_manager.ensure_tables_exist()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader):
            if limit and idx >= int(limit):
                break
            term = (row.get("term") or "").strip()
            seed_category = (row.get("seed_category") or "").strip() or None
            if not term:
                continue
            if database_manager.upsert_term(term, database_manager.DEFAULT_PRIORITY, seed_category=seed_category):
                inserted += 1
    return inserted


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Seed compiler queue from normalized terms")
    parser.add_argument("--from", dest="source", choices=["db", "csv"], default="db")
    parser.add_argument("--csv", default=str(DEFAULT_NORMALIZED_CSV))
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    limit = int(args.limit) if args.limit else None
    if args.source == "db":
        inserted = _seed_from_db(limit)
    else:
        inserted = _seed_from_csv(Path(args.csv).resolve(), limit)
    LOGGER.info("Inserted %s new terms into task_queue", inserted)


if __name__ == "__main__":
    main()

