"""SQLite-backed queue manager for ingredient processing."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Iterable, List, Tuple

from .config import load_settings

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"


class StateStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_queue (
                    term TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_error TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def seed_terms(self, terms: Iterable[str]) -> int:
        inserted = 0
        with self._get_conn() as conn:
            for term in terms:
                term = term.strip()
                if not term:
                    continue
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO processing_queue(term, status) VALUES(?, ?)",
                        (term, STATUS_PENDING),
                    )
                    inserted += conn.total_changes
                except sqlite3.DatabaseError:
                    continue
        return inserted

    def fetch_next_terms(self, limit: int) -> List[str]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT term FROM processing_queue WHERE status = ? LIMIT ?",
                (STATUS_PENDING, limit),
            ).fetchall()
        return [row[0] for row in rows]

    def mark_status(self, term: str, status: str, error: str | None = None) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE processing_queue
                   SET status = ?, last_error = ?, updated_at = CURRENT_TIMESTAMP
                 WHERE term = ?
                """,
                (status, error, term),
            )

    def summary(self) -> List[Tuple[str, int]]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) as count FROM processing_queue GROUP BY status"
            ).fetchall()
        return [(row[0], row[1]) for row in rows]


def cmd_init(args: argparse.Namespace) -> None:
    settings = load_settings()
    store = StateStore(settings.db_path)
    with settings.terms_path.open("r", encoding="utf-8") as handle:
        inserted = store.seed_terms(handle.readlines())
    print(f"Seeded {inserted} terms from {settings.terms_path}")


def cmd_summary(args: argparse.Namespace) -> None:
    settings = load_settings()
    store = StateStore(settings.db_path)
    for status, count in store.summary():
        print(f"{status:>11}: {count}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="State store utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Seed the queue from terms.txt")
    init_parser.set_defaults(func=cmd_init)

    summary_parser = sub.add_parser("summary", help="Show processing counts")
    summary_parser.set_defaults(func=cmd_summary)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
