"""SQLite-backed task queue utilities for the iterative compiler."""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from sqlalchemy import Column, DateTime, Integer, String, create_engine, select, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "compiler_state.db"
DB_PATH = Path(os.environ.get("COMPILER_DB_PATH", DEFAULT_DB_PATH))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()


DEFAULT_PRIORITY = 5
MIN_PRIORITY = 1
MAX_PRIORITY = 10


class TaskQueue(Base):
    """ORM model representing a queued ingredient term."""

    __tablename__ = "task_queue"

    term = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="pending")
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)
    priority = Column(Integer, nullable=False, default=DEFAULT_PRIORITY)


VALID_STATUSES = {"pending", "processing", "completed", "error"}


def ensure_tables_exist() -> None:
    """Create the task_queue table if it does not already exist."""

    Base.metadata.create_all(engine)
    _ensure_priority_column()


def _ensure_priority_column() -> None:
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(task_queue)")).fetchall()
        column_names = {row[1] for row in columns}
        if "priority" not in column_names:
            conn.execute(
                text("ALTER TABLE task_queue ADD COLUMN priority INTEGER NOT NULL DEFAULT :default"),
                {"default": DEFAULT_PRIORITY},
            )
            LOGGER.info("Added priority column to task_queue")


@contextmanager
def get_session() -> Iterable[Session]:
    """Provide a transactional scope around a series of operations."""

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _sanitize_priority(value) -> int:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return DEFAULT_PRIORITY
    return max(MIN_PRIORITY, min(MAX_PRIORITY, priority))


def _load_terms(terms_file_path: Path) -> List[Tuple[str, int]]:
    """Read the seed term list from JSON or newline-delimited text, including priority metadata."""

    if not terms_file_path.exists():
        raise FileNotFoundError(f"Seed terms file not found: {terms_file_path}")

    raw_text = terms_file_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    entries: dict[str, int] = {}

    # Attempt JSON first (expecting an array of objects or strings)
    try:
        data = json.loads(raw_text)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, str):
                    term = item.strip()
                    if term:
                        entries[term] = max(entries.get(term, MIN_PRIORITY), DEFAULT_PRIORITY)
                elif isinstance(item, dict):
                    term = str(item.get("term") or item.get("name") or "").strip()
                    if not term:
                        continue
                    priority = _sanitize_priority(item.get("priority") or item.get("priority_score"))
                    existing = entries.get(term)
                    if existing is None or priority > existing:
                        entries[term] = priority
        else:
            raise json.JSONDecodeError("Not a list", raw_text, 0)
    except json.JSONDecodeError:
        # Fallback to newline-delimited text
        for line in raw_text.splitlines():
            term = line.strip()
            if term:
                entries[term] = max(entries.get(term, MIN_PRIORITY), DEFAULT_PRIORITY)

    deduped_sorted_terms = sorted(entries.items(), key=lambda item: item[0])
    return deduped_sorted_terms


def initialize_queue(terms_file_path: str | os.PathLike[str]) -> int:
    """Populate the queue with seed terms.

    Args:
        terms_file_path: Path to a JSON array or newline-delimited list of terms.

    Returns:
        Number of terms inserted.
    """

    ensure_tables_exist()
    terms_path = Path(terms_file_path)
    term_entries = _load_terms(terms_path)
    if not term_entries:
        LOGGER.warning("No terms found in %s; queue not modified.", terms_path)
        return 0

    inserted = 0
    with get_session() as session:
        existing_rows = {
            row[0]: row[1]
            for row in session.execute(select(TaskQueue.term, TaskQueue.priority))
        }
        for term, priority in term_entries:
            normalized_priority = _sanitize_priority(priority)
            existing_priority = existing_rows.get(term)
            if existing_priority is not None:
                if normalized_priority > existing_priority:
                    session.query(TaskQueue).filter(TaskQueue.term == term).update(
                        {"priority": normalized_priority, "last_updated": datetime.utcnow()}
                    )
                    LOGGER.debug("Elevated priority for %s from %s to %s", term, existing_priority, normalized_priority)
                continue
            session.add(
                TaskQueue(
                    term=term,
                    status="pending",
                    last_updated=datetime.utcnow(),
                    priority=normalized_priority,
                )
            )
            inserted += 1

    if inserted:
        LOGGER.info("Inserted %s new terms into the queue.", inserted)
    else:
        LOGGER.info("Queue already contained all provided terms; nothing inserted.")
    return inserted


def get_next_pending_task(min_priority: int = MIN_PRIORITY) -> Optional[tuple[str, int]]:
    """Return the next pending term honoring priority sorting."""

    ensure_tables_exist()
    with get_session() as session:
        task: Optional[TaskQueue] = (
            session.query(TaskQueue)
            .filter(
                TaskQueue.status == "pending",
                TaskQueue.priority >= max(MIN_PRIORITY, min_priority),
            )
            .order_by(TaskQueue.priority.desc(), TaskQueue.term.asc())
            .first()
        )
        if task:
            return task.term, task.priority
        return None


def update_task_status(term: str, status: str) -> None:
    """Update the status of a queue item."""

    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Valid options: {sorted(VALID_STATUSES)}")

    ensure_tables_exist()
    with get_session() as session:
        task: Optional[TaskQueue] = session.get(TaskQueue, term)
        if not task:
            raise LookupError(f"Task '{term}' does not exist in the queue.")
        task.status = status
        task.last_updated = datetime.utcnow()


def queue_is_empty() -> bool:
    """Return True if there are no records in the queue."""

    ensure_tables_exist()
    with get_session() as session:
        exists = session.query(TaskQueue.term).first()
        return exists is None


def get_queue_summary() -> dict:
    """Return a count of tasks grouped by status for observability."""

    ensure_tables_exist()
    summary = {status: 0 for status in VALID_STATUSES}
    with get_session() as session:
        rows = session.execute(
            select(TaskQueue.status)
        )
        for (status,) in rows:
            summary[status] = summary.get(status, 0) + 1
    summary["total"] = sum(summary.values())
    return summary
