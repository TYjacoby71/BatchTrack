"""Enqueue normalized base terms into the compiler task queue.

One-time pipeline rule:
- Seed ONLY from the `normalized_terms` table.
- No CSV fallback. The ingestion system is DB-first and does not rely on exports.
"""

from __future__ import annotations

import argparse
import logging

from . import database_manager

LOGGER = logging.getLogger(__name__)


def _seed_from_db(limit: int | None) -> int:
    database_manager.ensure_tables_exist()
    inserted = 0
    priority_map = database_manager.build_term_priority_map()
    with database_manager.get_session() as session:
        q = session.query(database_manager.NormalizedTerm).order_by(database_manager.NormalizedTerm.term.asc())
        if limit:
            q = q.limit(int(limit))
        rows = q.all()
        for r in rows:
            priority = int(priority_map.get(r.term, database_manager.DEFAULT_PRIORITY))
            # Ensure 1..10 priority contract.
            priority = max(database_manager.MIN_PRIORITY, min(database_manager.MAX_PRIORITY, priority))
            if database_manager.upsert_term(r.term, priority, seed_category=r.seed_category):
                inserted += 1
    return inserted


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Seed compiler queue from normalized terms")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    limit = int(args.limit) if args.limit else None
    inserted = _seed_from_db(limit)
    LOGGER.info("Inserted %s new terms into task_queue", inserted)


if __name__ == "__main__":
    main()

