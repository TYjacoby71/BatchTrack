"""Maintenance helpers for batch compilation backfills."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func

from . import database_manager

DEFAULT_MARK_COMPLETE_LIMIT = 2406


def _require_db(path: str | Path) -> Path:
    db_path = Path(path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    database_manager.configure_db_path(db_path)
    database_manager.ensure_tables_exist()
    return db_path


def backfill_stage1_compilation_ranks() -> int:
    """Assign compilation ranks to Stage 1 records missing them."""
    with database_manager.get_session() as session:
        max_rank = session.query(func.max(database_manager.CompiledClusterRecord.compilation_rank)).scalar() or 0
        rows = (
            session.query(database_manager.CompiledClusterRecord)
            .filter(database_manager.CompiledClusterRecord.term_status == "done")
            .filter(database_manager.CompiledClusterRecord.compilation_rank.is_(None))
            .order_by(
                database_manager.CompiledClusterRecord.term_compiled_at.asc().nulls_last(),
                database_manager.CompiledClusterRecord.updated_at.asc(),
                database_manager.CompiledClusterRecord.cluster_id.asc(),
            )
            .all()
        )
        if not rows:
            return 0
        now = datetime.now(timezone.utc)
        rank = int(max_rank)
        for rec in rows:
            rank += 1
            rec.compilation_rank = rank
            rec.updated_at = now
        session.commit()
        return len(rows)


def mark_first_compiled_items_complete(limit: int) -> int:
    """Mark the first N compiled items as done when they already have payloads."""
    if limit <= 0:
        return 0
    with database_manager.get_session() as session:
        rows = (
            session.query(database_manager.CompiledClusterItemRecord)
            .filter(database_manager.CompiledClusterItemRecord.item_status != "done")
            .filter(database_manager.CompiledClusterItemRecord.item_json.isnot(None))
            .filter(database_manager.CompiledClusterItemRecord.item_json != "")
            .filter(database_manager.CompiledClusterItemRecord.item_json != "{}")
            .order_by(
                database_manager.CompiledClusterItemRecord.item_compiled_at.asc().nulls_last(),
                database_manager.CompiledClusterItemRecord.id.asc(),
            )
            .limit(int(limit))
            .all()
        )
        if not rows:
            return 0
        now = datetime.now(timezone.utc)
        for row in rows:
            row.item_status = "done"
            row.item_error = None
            if row.item_compiled_at is None:
                row.item_compiled_at = now
            row.updated_at = now
        session.commit()
        return len(rows)


def reset_batch_pending() -> tuple[int, int]:
    """Reset batch_pending statuses back to pending."""
    with database_manager.get_session() as session:
        now = datetime.now(timezone.utc)
        term_count = (
            session.query(database_manager.CompiledClusterRecord)
            .filter(database_manager.CompiledClusterRecord.term_status == "batch_pending")
            .update(
                {
                    database_manager.CompiledClusterRecord.term_status: "pending",
                    database_manager.CompiledClusterRecord.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        item_count = (
            session.query(database_manager.CompiledClusterItemRecord)
            .filter(database_manager.CompiledClusterItemRecord.item_status == "batch_pending")
            .update(
                {
                    database_manager.CompiledClusterItemRecord.item_status: "pending",
                    database_manager.CompiledClusterItemRecord.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        session.commit()
        return int(term_count or 0), int(item_count or 0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch maintenance utilities")
    parser.add_argument("--db-path", required=True, help="Path to compiler DB")
    parser.add_argument("--assign-stage1-ranks", action="store_true", help="Backfill Stage 1 compilation_rank")
    parser.add_argument(
        "--mark-first-items-complete",
        type=int,
        help=f"Mark first N compiled items done (default {DEFAULT_MARK_COMPLETE_LIMIT} when --all).",
    )
    parser.add_argument("--reset-batch-pending", action="store_true", help="Reset batch_pending to pending")
    parser.add_argument("--all", action="store_true", help="Run all maintenance actions")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not (
        args.all
        or args.assign_stage1_ranks
        or args.mark_first_items_complete is not None
        or args.reset_batch_pending
    ):
        raise SystemExit("No actions specified. Use --all or individual flags.")

    _require_db(args.db_path)

    if args.all or args.assign_stage1_ranks:
        count = backfill_stage1_compilation_ranks()
        print(f"Stage 1 rank backfill: {count} rows updated")

    if args.all or args.mark_first_items_complete is not None:
        limit = (
            int(args.mark_first_items_complete)
            if args.mark_first_items_complete is not None
            else DEFAULT_MARK_COMPLETE_LIMIT
        )
        count = mark_first_compiled_items_complete(limit)
        print(f"Marked {count} compiled items as done (limit={limit})")

    if args.all or args.reset_batch_pending:
        term_count, item_count = reset_batch_pending()
        print(f"Reset batch_pending: {term_count} terms, {item_count} items")


if __name__ == "__main__":
    main()
