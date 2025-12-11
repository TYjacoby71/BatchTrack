"""SQLite-backed task queue utilities for the iterative compiler."""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy import Column, DateTime, String, create_engine, select
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


class TaskQueue(Base):
    """ORM model representing a queued ingredient term."""

    __tablename__ = "task_queue"

    term = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="pending")
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)


VALID_STATUSES = {"pending", "processing", "completed", "error"}


def ensure_tables_exist() -> None:
    """Create the task_queue table if it does not already exist."""

    Base.metadata.create_all(engine)


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


def _load_terms(terms_file_path: Path) -> List[str]:
    """Read the seed term list from JSON or newline-delimited text."""

    if not terms_file_path.exists():
        raise FileNotFoundError(f"Seed terms file not found: {terms_file_path}")

    raw_text = terms_file_path.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []

    terms: List[str] = []

    # Attempt JSON first (expecting an array of strings)
    try:
        data = json.loads(raw_text)
        if isinstance(data, list):
            terms = [str(item).strip() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        # Fallback to newline-delimited text
        terms = [line.strip() for line in raw_text.splitlines() if line.strip()]

    deduped_sorted_terms = sorted(dict.fromkeys(terms))
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
    terms = _load_terms(terms_path)
    if not terms:
        LOGGER.warning("No terms found in %s; queue not modified.", terms_path)
        return 0

    inserted = 0
    with get_session() as session:
        existing_terms = {
            row[0]
            for row in session.execute(select(TaskQueue.term))
        }
        for term in terms:
            if term in existing_terms:
                continue
            session.add(TaskQueue(term=term, status="pending", last_updated=datetime.utcnow()))
            inserted += 1

    if inserted:
        LOGGER.info("Inserted %s new terms into the queue.", inserted)
    else:
        LOGGER.info("Queue already contained all provided terms; nothing inserted.")
    return inserted


def get_next_pending_task() -> Optional[str]:
    """Return the next alphabetically pending term."""

    ensure_tables_exist()
    with get_session() as session:
        task: Optional[TaskQueue] = (
            session.query(TaskQueue)
            .filter(TaskQueue.status == "pending")
            .order_by(TaskQueue.term.asc())
            .first()
        )
        return task.term if task else None


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
