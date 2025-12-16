"""SQLite-backed task queue utilities for the iterative compiler."""
from __future__ import annotations

import json
import logging
import os
import re
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine, select, text
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
    # Stage 1 seed category cursor (optional). When set, the term builder can ratchet by
    # (seed_category, initial) instead of just initial.
    seed_category = Column(String, nullable=True, default=None)


class IngredientRecord(Base):
    """Compiled ingredient payload (stage 2 output), keyed by queued base term."""

    __tablename__ = "ingredients"

    term = Column(String, primary_key=True)
    seed_category = Column(String, nullable=True, default=None)

    category = Column(String, nullable=True, default=None)
    botanical_name = Column(String, nullable=True, default=None)
    inci_name = Column(String, nullable=True, default=None)
    cas_number = Column(String, nullable=True, default=None)
    short_description = Column(Text, nullable=True, default=None)
    detailed_description = Column(Text, nullable=True, default=None)

    payload_json = Column(Text, nullable=False, default="{}")
    compiled_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class IngredientItemRecord(Base):
    """Compiled purchasable item for a base ingredient (base + variation + physical_form)."""

    __tablename__ = "ingredient_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingredient_term = Column(String, ForeignKey("ingredients.term"), nullable=False)

    # Derived (not trusted from AI).
    item_name = Column(String, nullable=False)

    # Split fields.
    variation = Column(String, nullable=True, default="")
    physical_form = Column(String, nullable=True, default="")

    # Display helpers.
    form_bypass = Column(Boolean, nullable=False, default=False)
    variation_bypass = Column(Boolean, nullable=False, default=False)

    # Full item JSON for the rest of attributes.
    item_json = Column(Text, nullable=False, default="{}")

    # Common scalar/range fields promoted for querying (nullable where absent).
    shelf_life_days = Column(Integer, nullable=True, default=None)

    storage_temp_c_min = Column(Integer, nullable=True, default=None)
    storage_temp_c_max = Column(Integer, nullable=True, default=None)
    storage_humidity_max = Column(Integer, nullable=True, default=None)

    sap_naoh = Column(String, nullable=True, default=None)
    sap_koh = Column(String, nullable=True, default=None)
    iodine_value = Column(String, nullable=True, default=None)
    flash_point_c = Column(String, nullable=True, default=None)

    melting_point_c_min = Column(String, nullable=True, default=None)
    melting_point_c_max = Column(String, nullable=True, default=None)

    ph_min = Column(String, nullable=True, default=None)
    ph_max = Column(String, nullable=True, default=None)


class IngredientItemValue(Base):
    """Normalized list values for item attributes (tags, applications, origins, etc.)."""

    __tablename__ = "ingredient_item_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("ingredient_items.id"), nullable=False)
    field = Column(String, nullable=False)  # e.g. applications, function_tags, certifications, synonyms
    value = Column(String, nullable=False)


class SourceTerm(Base):
    """Deterministic candidate term extracted from external CSV sources."""

    __tablename__ = "source_terms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    seed_category = Column(String, nullable=False)
    source = Column(String, nullable=False)


class NormalizedTerm(Base):
    """Normalized base ingredient term extracted from sources (pre-compile)."""

    __tablename__ = "normalized_terms"

    term = Column(String, primary_key=True)
    seed_category = Column(String, nullable=True, default=None)

    botanical_name = Column(String, nullable=True, default=None)
    inci_name = Column(String, nullable=True, default=None)
    cas_number = Column(String, nullable=True, default=None)

    # A concise canonical description if available from sources.
    description = Column(Text, nullable=True, default=None)

    # Full aggregated source payload (small, merged) for inspection.
    sources_json = Column(Text, nullable=False, default="{}")
    normalized_at = Column(DateTime, nullable=False, default=datetime.utcnow)


VALID_STATUSES = {"pending", "processing", "completed", "error"}


def ensure_tables_exist() -> None:
    """Create the task_queue table if it does not already exist."""

    Base.metadata.create_all(engine)
    _ensure_priority_column()
    _ensure_seed_category_column()
    _ensure_ingredient_item_columns()


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


def _ensure_seed_category_column() -> None:
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(task_queue)")).fetchall()
        column_names = {row[1] for row in columns}
        if "seed_category" not in column_names:
            conn.execute(
                text("ALTER TABLE task_queue ADD COLUMN seed_category TEXT"),
            )
            LOGGER.info("Added seed_category column to task_queue")


def _ensure_ingredient_item_columns() -> None:
    """Add promoted scalar/range columns to ingredient_items if missing."""
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(ingredient_items)")).fetchall()
        column_names = {row[1] for row in columns}

        additions = [
            ("shelf_life_days", "INTEGER"),
            ("storage_temp_c_min", "INTEGER"),
            ("storage_temp_c_max", "INTEGER"),
            ("storage_humidity_max", "INTEGER"),
            ("sap_naoh", "TEXT"),
            ("sap_koh", "TEXT"),
            ("iodine_value", "TEXT"),
            ("flash_point_c", "TEXT"),
            ("melting_point_c_min", "TEXT"),
            ("melting_point_c_max", "TEXT"),
            ("ph_min", "TEXT"),
            ("ph_max", "TEXT"),
        ]

        for name, col_type in additions:
            if name in column_names:
                continue
            conn.execute(text(f"ALTER TABLE ingredient_items ADD COLUMN {name} {col_type}"))
            LOGGER.info("Added %s column to ingredient_items", name)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _extract_parenthetical_variation(item_name: str, base: str) -> str:
    """Best-effort: parse 'Base (Variation)' -> 'Variation'."""
    if not item_name or not base:
        return ""
    escaped = re.escape(base.strip())
    match = re.match(rf"^{escaped}\s*\((.+)\)\s*$", item_name.strip())
    return (match.group(1).strip() if match else "")


def _derive_item_name(base: str, variation: str, variation_bypass: bool) -> str:
    base_clean = (base or "").strip()
    var_clean = (variation or "").strip()
    if not base_clean:
        return ""
    if not var_clean or variation_bypass:
        return base_clean
    return f"{base_clean} ({var_clean})"


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


def upsert_terms(term_entries: Iterable[Tuple[str, int]]) -> int:
    """Upsert terms directly into the queue (preferred for large runs).

    This avoids requiring a giant `terms.json` file as an intermediate artifact.

    Returns:
        Number of newly inserted terms.
    """
    ensure_tables_exist()
    inserted = 0
    with get_session() as session:
        existing_rows = {
            row[0]: row[1]
            for row in session.execute(select(TaskQueue.term, TaskQueue.priority))
        }
        for term, priority in term_entries:
            cleaned = (term or "").strip()
            if not cleaned:
                continue
            normalized_priority = _sanitize_priority(priority)
            existing_priority = existing_rows.get(cleaned)
            if existing_priority is not None:
                if normalized_priority > existing_priority:
                    session.query(TaskQueue).filter(TaskQueue.term == cleaned).update(
                        {"priority": normalized_priority, "last_updated": datetime.utcnow()}
                    )
                continue
            session.add(
                TaskQueue(
                    term=cleaned,
                    status="pending",
                    last_updated=datetime.utcnow(),
                    priority=normalized_priority,
                )
            )
            inserted += 1
    if inserted:
        LOGGER.info("Inserted %s new terms into the queue via upsert.", inserted)
    return inserted


def get_all_terms() -> List[Tuple[str, int]]:
    """Return all terms currently known to the queue (term, priority)."""
    ensure_tables_exist()
    with get_session() as session:
        rows = session.execute(select(TaskQueue.term, TaskQueue.priority)).all()
        return [(term, priority) for term, priority in rows]


def get_last_term() -> Optional[str]:
    """Return the last term in lexicographic order (case-insensitive), or None."""
    ensure_tables_exist()
    with get_session() as session:
        row = (
            session.execute(
                select(TaskQueue.term)
                .order_by(TaskQueue.term.collate("NOCASE").desc(), TaskQueue.term.desc())
                .limit(1)
            )
            .first()
        )
        return row[0] if row else None


def get_last_term_for_initial(initial: str) -> Optional[str]:
    """Return the last term (A..Z) for a given initial, or None if none exist.

    Notes:
    - Matching is case-insensitive for ASCII letters.
    - Ordering is case-insensitive, then case-sensitive as a tiebreaker.
    """
    ensure_tables_exist()
    letter = (initial or "").strip()[:1].upper()
    if not letter:
        return None

    with get_session() as session:
        row = (
            session.execute(
                select(TaskQueue.term)
                .where(TaskQueue.term.collate("NOCASE").like(f"{letter}%"))
                .order_by(TaskQueue.term.collate("NOCASE").desc(), TaskQueue.term.desc())
                .limit(1)
            )
            .first()
        )
        return row[0] if row else None


def get_last_term_for_initial_and_seed_category(initial: str, seed_category: str) -> Optional[str]:
    """Return the last term for a given initial constrained to a seed_category."""
    ensure_tables_exist()
    letter = (initial or "").strip()[:1].upper()
    category = (seed_category or "").strip()
    if not letter or not category:
        return None

    with get_session() as session:
        row = (
            session.execute(
                select(TaskQueue.term)
                .where(
                    TaskQueue.seed_category == category,
                    TaskQueue.term.collate("NOCASE").like(f"{letter}%"),
                )
                .order_by(TaskQueue.term.collate("NOCASE").desc(), TaskQueue.term.desc())
                .limit(1)
            )
            .first()
        )
        return row[0] if row else None


def upsert_term(term: str, priority: int, *, seed_category: str | None = None) -> bool:
    """Upsert a single term and commit immediately.

    Returns:
        True if a new term was inserted, False if it already existed (priority may still be updated).
    """
    ensure_tables_exist()
    cleaned = (term or "").strip()
    if not cleaned:
        return False

    normalized_priority = _sanitize_priority(priority)
    cleaned_category = (seed_category or "").strip() or None
    with get_session() as session:
        existing: Optional[TaskQueue] = session.get(TaskQueue, cleaned)
        if existing is not None:
            if normalized_priority > int(existing.priority or DEFAULT_PRIORITY):
                existing.priority = normalized_priority
                existing.last_updated = datetime.utcnow()
            # Backfill seed_category if missing or changed.
            if cleaned_category and (existing.seed_category or "").strip() != cleaned_category:
                existing.seed_category = cleaned_category
            return False

        session.add(
            TaskQueue(
                term=cleaned,
                status="pending",
                last_updated=datetime.utcnow(),
                priority=normalized_priority,
                seed_category=cleaned_category,
            )
        )
        return True


def get_next_pending_task(min_priority: int = MIN_PRIORITY) -> Optional[tuple[str, int, str | None]]:
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
            return task.term, task.priority, (task.seed_category or None)
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


def upsert_compiled_ingredient(term: str, payload: dict, *, seed_category: str | None = None) -> None:
    """Persist the compiled ingredient + items into the DB (replaces JSON files)."""
    ensure_tables_exist()
    cleaned = (term or "").strip()
    if not cleaned:
        raise ValueError("term is required")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    ingredient = payload.get("ingredient") if isinstance(payload.get("ingredient"), dict) else {}
    # Enforce stability: queued term is canonical base.
    ingredient["common_name"] = cleaned
    payload["ingredient"] = ingredient

    cleaned_category = (seed_category or "").strip() or None
    category = (ingredient.get("category") or "").strip() or None
    botanical_name = (ingredient.get("botanical_name") or "").strip() or None
    inci_name = (ingredient.get("inci_name") or "").strip() or None
    cas_number = (ingredient.get("cas_number") or "").strip() or None
    short_description = ingredient.get("short_description")
    detailed_description = ingredient.get("detailed_description")

    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    items = ingredient.get("items") if isinstance(ingredient.get("items"), list) else []

    with get_session() as session:
        record: Optional[IngredientRecord] = session.get(IngredientRecord, cleaned)
        if record is None:
            record = IngredientRecord(term=cleaned)
            session.add(record)

        record.seed_category = cleaned_category
        record.category = category
        record.botanical_name = botanical_name
        record.inci_name = inci_name
        record.cas_number = cas_number
        if isinstance(short_description, str):
            record.short_description = short_description.strip()
        if isinstance(detailed_description, str):
            record.detailed_description = detailed_description.strip()
        record.payload_json = payload_json
        record.compiled_at = datetime.utcnow()

        # Replace items (deterministic; avoids partial merges).
        session.query(IngredientItemRecord).filter(IngredientItemRecord.ingredient_term == cleaned).delete()

        variation_forms = {
            "Essential Oil",
            "CO2 Extract",
            "Absolute",
            "Hydrosol",
            "Tincture",
            "Glycerite",
            "Distillate",
            "Oleoresin",
            "Alcohol Extract",
            "Vinegar Extract",
            "Powdered Extract",
            "Supercritical Extract",
            "Lye Solution",
            "Stock Solution",
        }

        for raw_item in items:
            if not isinstance(raw_item, dict):
                continue

            variation = (raw_item.get("variation") or "").strip()
            if not variation:
                variation = _extract_parenthetical_variation(str(raw_item.get("item_name") or ""), cleaned)

            physical_form = (raw_item.get("physical_form") or "").strip()
            # If the model put a variation into physical_form, fix it here.
            if physical_form in variation_forms and not variation:
                variation = physical_form
                physical_form = "Oil" if "Oil" in variation else "Liquid"
            form_bypass = _coerce_bool(raw_item.get("form_bypass"), default=False)
            variation_bypass = _coerce_bool(raw_item.get("variation_bypass"), default=False)

            derived_item_name = _derive_item_name(cleaned, variation, variation_bypass)
            if not derived_item_name:
                continue

            cleaned_item = dict(raw_item)
            cleaned_item["variation"] = variation
            cleaned_item["physical_form"] = physical_form
            cleaned_item["item_name"] = derived_item_name
            # Discard usage_rate_percent (requested).
            specs = cleaned_item.get("specifications")
            if isinstance(specs, dict) and "usage_rate_percent" in specs:
                specs.pop("usage_rate_percent", None)
                cleaned_item["specifications"] = specs
            item_json = json.dumps(cleaned_item, ensure_ascii=False, sort_keys=True)

            # Promote common scalar/range fields.
            shelf_life_days = cleaned_item.get("shelf_life_days")
            shelf_life_days = int(shelf_life_days) if isinstance(shelf_life_days, (int, float)) else None

            storage = cleaned_item.get("storage") if isinstance(cleaned_item.get("storage"), dict) else {}
            temp = storage.get("temperature_celsius") if isinstance(storage.get("temperature_celsius"), dict) else {}
            humidity = storage.get("humidity_percent") if isinstance(storage.get("humidity_percent"), dict) else {}
            st_min = temp.get("min")
            st_max = temp.get("max")
            hm = humidity.get("max")
            st_min = int(st_min) if isinstance(st_min, (int, float)) else None
            st_max = int(st_max) if isinstance(st_max, (int, float)) else None
            hm = int(hm) if isinstance(hm, (int, float)) else None

            specs = cleaned_item.get("specifications") if isinstance(cleaned_item.get("specifications"), dict) else {}
            mp = specs.get("melting_point_celsius") if isinstance(specs.get("melting_point_celsius"), dict) else {}
            ph = specs.get("ph_range") if isinstance(specs.get("ph_range"), dict) else {}

            item_row = IngredientItemRecord(
                ingredient_term=cleaned,
                item_name=derived_item_name,
                variation=variation,
                physical_form=physical_form,
                form_bypass=form_bypass,
                variation_bypass=variation_bypass,
                item_json=item_json,
                shelf_life_days=shelf_life_days,
                storage_temp_c_min=st_min,
                storage_temp_c_max=st_max,
                storage_humidity_max=hm,
                sap_naoh=str(specs.get("sap_naoh")) if specs.get("sap_naoh") not in (None, "") else None,
                sap_koh=str(specs.get("sap_koh")) if specs.get("sap_koh") not in (None, "") else None,
                iodine_value=str(specs.get("iodine_value")) if specs.get("iodine_value") not in (None, "") else None,
                flash_point_c=str(specs.get("flash_point_celsius")) if specs.get("flash_point_celsius") not in (None, "") else None,
                melting_point_c_min=str(mp.get("min")) if mp.get("min") not in (None, "") else None,
                melting_point_c_max=str(mp.get("max")) if mp.get("max") not in (None, "") else None,
                ph_min=str(ph.get("min")) if ph.get("min") not in (None, "") else None,
                ph_max=str(ph.get("max")) if ph.get("max") not in (None, "") else None,
            )
            session.add(item_row)
            session.flush()  # obtain item_row.id for child values

            def _add_values(field: str, values: Any) -> None:
                if not values:
                    return
                if isinstance(values, str):
                    vals = [values]
                elif isinstance(values, list):
                    vals = [v for v in values if isinstance(v, str)]
                else:
                    return
                for v in vals:
                    vv = v.strip()
                    if not vv:
                        continue
                    session.add(IngredientItemValue(item_id=item_row.id, field=field, value=vv))

            _add_values("synonyms", cleaned_item.get("synonyms"))
            _add_values("applications", cleaned_item.get("applications"))
            _add_values("function_tags", cleaned_item.get("function_tags"))
            _add_values("safety_tags", cleaned_item.get("safety_tags"))
            _add_values("sds_hazards", cleaned_item.get("sds_hazards"))

            sourcing = cleaned_item.get("sourcing") if isinstance(cleaned_item.get("sourcing"), dict) else {}
            _add_values("certifications", sourcing.get("certifications"))
            _add_values("common_origins", sourcing.get("common_origins"))
            _add_values("supply_risks", sourcing.get("supply_risks"))


def upsert_source_terms(rows: Iterable[tuple[str, str, str]]) -> int:
    """Upsert (name, seed_category, source) into source_terms; returns newly inserted count."""
    ensure_tables_exist()
    inserted = 0
    with get_session() as session:
        existing = set(session.query(SourceTerm.name, SourceTerm.seed_category, SourceTerm.source).all())
        for name, seed_category, source in rows:
            cleaned = (name or "").strip()
            cat = (seed_category or "").strip()
            src = (source or "").strip()
            if not cleaned or not cat or not src:
                continue
            key = (cleaned, cat, src)
            if key in existing:
                continue
            session.add(SourceTerm(name=cleaned, seed_category=cat, source=src))
            existing.add(key)
            inserted += 1
    return inserted


def get_next_source_term(seed_category: str, initial: str, start_after: str) -> Optional[str]:
    """Return next deterministic source term for (seed_category, initial) after start_after."""
    ensure_tables_exist()
    cat = (seed_category or "").strip()
    letter = (initial or "").strip()[:1]
    after = (start_after or "").strip()
    if not cat or not letter:
        return None

    with get_session() as session:
        q = (
            session.query(SourceTerm.name)
            .filter(
                SourceTerm.seed_category == cat,
                SourceTerm.name.collate("NOCASE").like(f"{letter.upper()}%"),
            )
        )
        if after:
            q = q.filter(SourceTerm.name.collate("NOCASE") > after)
        row = q.order_by(SourceTerm.name.collate("NOCASE").asc(), SourceTerm.name.asc()).first()
        return row[0] if row else None


def upsert_normalized_terms(rows: Iterable[dict[str, Any]]) -> int:
    """Upsert normalized term records; returns count newly inserted."""
    ensure_tables_exist()
    inserted = 0
    with get_session() as session:
        existing = {r[0] for r in session.query(NormalizedTerm.term).all()}
        for row in rows:
            term = (row.get("term") or "").strip()
            if not term:
                continue
            if term in existing:
                # Update existing row (keep it fresh).
                record: Optional[NormalizedTerm] = session.get(NormalizedTerm, term)
                if record is None:
                    continue
            else:
                record = NormalizedTerm(term=term)
                session.add(record)
                existing.add(term)
                inserted += 1

            record.seed_category = (row.get("seed_category") or "").strip() or None
            record.botanical_name = (row.get("botanical_name") or "").strip() or None
            record.inci_name = (row.get("inci_name") or "").strip() or None
            record.cas_number = (row.get("cas_number") or "").strip() or None
            desc = row.get("description")
            if isinstance(desc, str) and desc.strip():
                record.description = desc.strip()
            sources_json = row.get("sources_json")
            if isinstance(sources_json, str) and sources_json.strip():
                record.sources_json = sources_json
            record.normalized_at = datetime.utcnow()
    return inserted


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
