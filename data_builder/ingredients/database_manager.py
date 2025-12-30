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

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine, exists, func, select, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

LOGGER = logging.getLogger(__name__)

from .taxonomy_constants import (
    INGREDIENT_CATEGORIES_PRIMARY,
    ORIGIN_TO_INGREDIENT_CATEGORIES,
    CATEGORY_ALLOWED_REFINEMENT_LEVELS,
    MASTER_CATEGORIES,
    MASTER_CATEGORY_RULE_SEED,
    ORIGINS,
    PHYSICAL_FORMS,
    REFINEMENT_LEVELS,
    VARIATIONS_CURATED,
)

def _derive_master_categories_from_rules(
    session: Session,
    *,
    ingredient_category: str,
    items: list[dict],
) -> list[str]:
    """Derive master categories using the DB rules table (data-driven)."""
    rules: dict[tuple[str, str], set[str]] = {}
    for r in session.query(MasterCategoryRule).all():
        rules.setdefault((r.source_type, r.source_value), set()).add(r.master_category)

    out: set[str] = set()

    # Base-level category
    for mc in rules.get(("ingredient_category", ingredient_category), set()):
        out.add(mc)

    # Item-derived
    for it in items:
        if not isinstance(it, dict):
            continue
        form = (it.get("physical_form") or "").strip()
        var = (it.get("variation") or "").strip()

        for mc in rules.get(("physical_form", form), set()):
            out.add(mc)
        for mc in rules.get(("variation", var), set()):
            out.add(mc)

        for tag in (it.get("function_tags") or []) if isinstance(it.get("function_tags"), list) else []:
            if isinstance(tag, str):
                for mc in rules.get(("function_tag", tag.strip()), set()):
                    out.add(mc)

        for app in (it.get("applications") or []) if isinstance(it.get("applications"), list) else []:
            if isinstance(app, str):
                for mc in rules.get(("application", app.strip()), set()):
                    out.add(mc)

    return sorted([m for m in out if m in MASTER_CATEGORIES])


def _guess_origin(ingredient: dict, term: str) -> str:
    value = (ingredient.get("origin") or "").strip()
    if value in ORIGINS:
        return value
    t = (term or "").lower()
    if any(k in t for k in ("oxide", "hydroxide", "carbonate", "chloride", "sulfate", "phosphate", "mica", "clay")):
        return "Mineral/Earth"
    if any(k in t for k in ("yeast", "xanthan", "culture", "scoby", "kefir")):
        return "Fermentation"
    # Heuristic: treat chemistry-like tokens as synthetic to avoid defaulting to Plant-Derived.
    # Examples: "2-acetyl-1-pyrroline", "disodium tetramethylhexadecenyl..."
    if any(ch.isdigit() for ch in t) and any(sym in t for sym in ("-", "/", ",")):
        return "Synthetic"
    if any(k in t for k in ("peg-", "ppg-", "poly", "copolymer", "acrylate", "quaternium", "dimethicone", "carbomer", "laureth", "ceteareth")):
        return "Synthetic"
    if ingredient.get("botanical_name"):
        return "Plant-Derived"
    # Conservative fallback: if nothing suggests mineral/ferment/synthetic, treat as Plant-Derived.
    return "Plant-Derived"


def _guess_primary_category(term: str, fallback: str | None = None) -> str:
    if fallback and fallback in INGREDIENT_CATEGORIES_PRIMARY:
        return fallback
    t = (term or "").lower()
    if any(k in t for k in ("salt", "epsom")):
        return "Salts"
    if "clay" in t:
        return "Clays"
    if any(k in t for k in ("acid", "vinegar")):
        return "Acids"
    if "sugar" in t:
        return "Sugars"
    if any(k in t for k in ("honey", "molasses", "maple", "agave", "syrup")):
        return "Liquid Sweeteners"
    if any(k in t for k in ("oat", "wheat", "rice", "corn", "barley", "starch", "flour")):
        return "Grains"
    if any(k in t for k in ("almond", "walnut", "hazelnut", "macadamia", "peanut")):
        return "Nuts"
    if any(k in t for k in ("chia", "sesame", "flax", "pumpkin seed", "poppy")):
        return "Seeds"
    if any(k in t for k in ("cinnamon", "turmeric", "ginger", "clove", "vanilla", "pepper")):
        return "Spices"
    if any(k in t for k in ("rose", "lavender", "hibiscus", "jasmine")):
        return "Flowers"
    if "root" in t:
        return "Roots"
    if "bark" in t:
        return "Barks"
    return "Herbs"


def _coerce_refinement(value: str | None) -> str:
    v = (value or "").strip()
    return v if v in REFINEMENT_LEVELS else "Other"


def _coerce_refinement_for_category(refinement: str | None, ingredient_category: str | None) -> str:
    """Apply category-specific refinement guardrails (best-effort)."""
    coerced = _coerce_refinement(refinement)
    cat = (ingredient_category or "").strip()
    allowed = CATEGORY_ALLOWED_REFINEMENT_LEVELS.get(cat)
    if not allowed:
        return coerced
    return coerced if coerced in allowed else "Other"


def _is_category_allowed_for_origin(origin: str | None, ingredient_category: str | None) -> bool:
    o = (origin or "").strip()
    c = (ingredient_category or "").strip()
    if not o or not c:
        return False
    allowed = ORIGIN_TO_INGREDIENT_CATEGORIES.get(o)
    if not allowed:
        return True
    return c in allowed


def _coerce_primary_category(value: str | None, term: str, seed_category: str | None) -> str:
    v = (value or "").strip()
    if v in INGREDIENT_CATEGORIES_PRIMARY:
        return v
    # Map older seed categories into primary.
    mapped = None
    if seed_category:
        sc = seed_category.strip()
        if sc in {"Culinary Herbs", "Medicinal Herbs", "Plants for Oils", "Plants for Butters"}:
            mapped = "Herbs"
        elif sc == "Roots & Barks" or sc == "Roots":
            mapped = "Roots"
        elif sc == "Barks":
            mapped = "Barks"
        elif sc == "Minerals":
            mapped = "Minerals"
        elif sc == "Salts":
            mapped = "Salts"
        elif sc == "Clays":
            mapped = "Clays"
        elif sc == "Acids":
            mapped = "Acids"
        elif sc == "Sugars":
            mapped = "Sugars"
        elif sc == "Liquid Sweeteners":
            mapped = "Liquid Sweeteners"
        elif sc == "Grains":
            mapped = "Grains"
        elif sc == "Seeds":
            mapped = "Seeds"
        elif sc == "Nuts":
            mapped = "Nuts"
        elif sc == "Spices":
            mapped = "Spices"
        elif sc == "Flowers":
            mapped = "Flowers"
        elif sc == "Vegetables":
            mapped = "Vegetables"
        elif sc == "Fruits & Berries":
            mapped = "Fruits & Berries"
    return _guess_primary_category(term, mapped)


def _derive_master_categories(ingredient_category: str, items: list[dict]) -> list[str]:
    """Deprecated: use _derive_master_categories_from_rules within a DB session."""
    return []
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

    # Primary ingredient category (single-select from curated Ingredient Categories).
    ingredient_category = Column(String, nullable=True, default=None)
    # Origin (required by SOP; stored as string enum).
    origin = Column(String, nullable=True, default=None)
    # Refinement (required by SOP; stored as string enum).
    refinement_level = Column(String, nullable=True, default=None)
    # Optional: natural source / precursor if base is derived.
    derived_from = Column(String, nullable=True, default=None)

    # Legacy/secondary category (from compiler category set, kept for compatibility).
    category = Column(String, nullable=True, default=None)
    botanical_name = Column(String, nullable=True, default=None)
    inci_name = Column(String, nullable=True, default=None)
    cas_number = Column(String, nullable=True, default=None)
    short_description = Column(Text, nullable=True, default=None)
    detailed_description = Column(Text, nullable=True, default=None)
    usage_restrictions = Column(Text, nullable=True, default=None)
    prohibited_flag = Column(Boolean, nullable=False, default=False)
    gras_status = Column(Boolean, nullable=False, default=False)
    ifra_category = Column(String, nullable=True, default=None)
    allergen_flag = Column(Boolean, nullable=False, default=False)
    colorant_flag = Column(Boolean, nullable=False, default=False)

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

    # Moderation controls: quarantine unapproved/hallucinated items without losing tokens.
    approved = Column(Boolean, nullable=False, default=True)
    status = Column(String, nullable=False, default="active")  # active|quarantine|rejected
    needs_review_reason = Column(Text, nullable=True, default=None)

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

    # Optional usage rates when present (kept, not required).
    usage_leave_on_max = Column(String, nullable=True, default=None)
    usage_rinse_off_max = Column(String, nullable=True, default=None)


class IngredientItemValue(Base):
    """Normalized list values for item attributes (tags, applications, origins, etc.)."""

    __tablename__ = "ingredient_item_values"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(Integer, ForeignKey("ingredient_items.id"), nullable=False)
    field = Column(String, nullable=False)  # e.g. applications, function_tags, certifications, synonyms
    value = Column(String, nullable=False)


class IngredientMasterCategory(Base):
    """Join table for ingredient -> master category (UX multi-select group)."""

    __tablename__ = "ingredient_master_categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingredient_term = Column(String, ForeignKey("ingredients.term"), nullable=False)
    master_category = Column(String, nullable=False)


class VariationTerm(Base):
    """Curated variation vocabulary (grows with review)."""

    __tablename__ = "variations"

    name = Column(String, primary_key=True)
    approved = Column(Boolean, nullable=False, default=True)


class PhysicalFormTerm(Base):
    """Curated physical form enum (~40)."""

    __tablename__ = "physical_forms"

    name = Column(String, primary_key=True)


class RefinementLevelTerm(Base):
    """Curated refinement level enum."""

    __tablename__ = "refinement_levels"

    name = Column(String, primary_key=True)


class MasterCategoryTerm(Base):
    """Curated master category list (UX dropdown)."""

    __tablename__ = "master_categories"

    name = Column(String, primary_key=True)


class IngredientCategoryTerm(Base):
    """Curated primary ingredient categories (base-level)."""

    __tablename__ = "ingredient_categories"

    name = Column(String, primary_key=True)


class MasterCategoryRule(Base):
    """Mapping rules: how master categories are derived from other fields."""

    __tablename__ = "master_category_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    master_category = Column(String, nullable=False)
    source_type = Column(String, nullable=False)  # ingredient_category|variation|physical_form|function_tag|application
    source_value = Column(String, nullable=False)


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

    # Deterministic SOP fields (best-effort; may be refined by compiler).
    ingredient_category = Column(String, nullable=True, default=None)
    origin = Column(String, nullable=True, default=None)
    refinement_level = Column(String, nullable=True, default=None)
    derived_from = Column(String, nullable=True, default=None)
    # Confidence scores (0-100) for deterministic assignments.
    ingredient_category_confidence = Column(Integer, nullable=True, default=None)
    origin_confidence = Column(Integer, nullable=True, default=None)
    refinement_confidence = Column(Integer, nullable=True, default=None)
    derived_from_confidence = Column(Integer, nullable=True, default=None)
    overall_confidence = Column(Integer, nullable=True, default=None)

    # Full aggregated source payload (small, merged) for inspection.
    sources_json = Column(Text, nullable=False, default="{}")
    normalized_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SourceItem(Base):
    """Raw source 'item' extracted from INCI/TGSC/etc.

    Item-first ingestion prevents source rows like 'Abies Alba Cone Oil' or
    'Beetroot Powder' from becoming queued *base* terms.

    A SourceItem may be linked to a derived base definition term, or left as an
    orphan when no safe linkage is possible yet.
    """

    __tablename__ = "source_items"

    # Deterministic key for this *source row* (1:1 traceability).
    key = Column(String, primary_key=True)

    source = Column(String, nullable=False)  # cosing|tgsc|...
    # Stable per-source row identity (e.g., CosIng Ref No, TGSC URL, or row index fallback).
    source_row_id = Column(String, nullable=True, default=None)
    source_row_number = Column(Integer, nullable=True, default=None)
    source_ref = Column(Text, nullable=True, default=None)  # e.g., CosIng Ref No / TGSC URL
    # Content-address fingerprint to support downstream dedupe/reconciliation.
    content_hash = Column(String, nullable=True, default=None)
    is_composite = Column(Boolean, nullable=False, default=False)

    raw_name = Column(Text, nullable=False)
    inci_name = Column(Text, nullable=True, default=None)
    cas_number = Column(String, nullable=True, default=None)

    # Parsed lineage linkage
    derived_term = Column(String, nullable=True, default=None)  # normalized base definition term
    derived_variation = Column(String, nullable=True, default=None)
    derived_physical_form = Column(String, nullable=True, default=None)

    # CAS list support (some sources provide multiple CAS numbers per row).
    cas_numbers_json = Column(Text, nullable=False, default="[]")

    # Deterministic best-effort taxonomy (may be blank if unknown)
    origin = Column(String, nullable=True, default=None)
    ingredient_category = Column(String, nullable=True, default=None)
    refinement_level = Column(String, nullable=True, default=None)

    status = Column(String, nullable=False, default="linked")  # linked|orphan|review
    needs_review_reason = Column(Text, nullable=True, default=None)

    # Full source row payload for traceability
    payload_json = Column(Text, nullable=False, default="{}")
    ingested_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SourceCatalogItem(Base):
    """Merged, de-duplicated item record across source datasets.

    Merge order (intent):
    - Start with CosIng as authoritative for INCI/CAS/EC + function + restriction + update date.
    - Overlay TGSC for common_name + physchem + odor/flavor + synonyms + URL when matched.

    Guardrail:
    - Never populate common_name from INCI. common_name should come from a source that
      explicitly provides a common/trade/common name (e.g. TGSC), otherwise leave null
      and allow the compiler to fill/alias later.
    """

    __tablename__ = "source_catalog_items"

    # Canonical identity key, typically "cas:<CAS>" or "ec:<EC>" or "inci:<normalized inci>".
    key = Column(String, primary_key=True)

    # Shared identifiers
    inci_name = Column(Text, nullable=True, default=None)
    cas_number = Column(String, nullable=True, default=None)
    ec_number = Column(String, nullable=True, default=None)

    # Common name (never set from INCI)
    common_name = Column(Text, nullable=True, default=None)

    # --- CosIng fields ---
    cosing_ref_nos_json = Column(Text, nullable=False, default="[]")  # JSON list of ref nos
    cosing_inn_name = Column(Text, nullable=True, default=None)
    cosing_ph_eur_name = Column(Text, nullable=True, default=None)
    cosing_description = Column(Text, nullable=True, default=None)
    cosing_restriction = Column(Text, nullable=True, default=None)
    cosing_functions_raw = Column(Text, nullable=True, default=None)
    cosing_functions_json = Column(Text, nullable=False, default="[]")  # JSON list
    cosing_update_date = Column(String, nullable=True, default=None)

    # --- TGSC fields ---
    tgsc_category = Column(String, nullable=True, default=None)
    tgsc_botanical_name = Column(Text, nullable=True, default=None)
    tgsc_einecs_number = Column(String, nullable=True, default=None)
    tgsc_fema_number = Column(String, nullable=True, default=None)
    tgsc_molecular_formula = Column(String, nullable=True, default=None)
    tgsc_molecular_weight = Column(String, nullable=True, default=None)
    tgsc_boiling_point = Column(String, nullable=True, default=None)
    tgsc_melting_point = Column(String, nullable=True, default=None)
    tgsc_density = Column(String, nullable=True, default=None)
    tgsc_odor_description = Column(Text, nullable=True, default=None)
    tgsc_flavor_description = Column(Text, nullable=True, default=None)
    tgsc_description = Column(Text, nullable=True, default=None)
    tgsc_uses = Column(Text, nullable=True, default=None)
    tgsc_safety_notes = Column(Text, nullable=True, default=None)
    tgsc_solubility = Column(Text, nullable=True, default=None)
    tgsc_synonyms = Column(Text, nullable=True, default=None)
    tgsc_natural_occurrence = Column(Text, nullable=True, default=None)
    tgsc_url = Column(Text, nullable=True, default=None)

    # Provenance
    sources_json = Column(Text, nullable=False, default="{}")  # merged source refs
    merged_at = Column(DateTime, nullable=False, default=datetime.utcnow)


VALID_STATUSES = {"pending", "processing", "completed", "error"}


def ensure_tables_exist() -> None:
    """Create the task_queue table if it does not already exist."""

    Base.metadata.create_all(engine)
    _ensure_priority_column()
    _ensure_seed_category_column()
    _ensure_ingredient_item_columns()
    _ensure_ingredient_columns()
    _ensure_normalized_term_columns()
    _seed_taxonomy_tables()
    _ensure_source_item_indexes()
    _ensure_source_item_columns()
    _ensure_source_catalog_indexes()


def _ensure_source_item_indexes() -> None:
    """Best-effort indexing for source_items (SQLite-safe)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_items_source ON source_items(source)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_items_status ON source_items(status)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_items_derived_term ON source_items(derived_term)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_items_source_row_id ON source_items(source_row_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_items_content_hash ON source_items(content_hash)"))
    except Exception:  # pragma: no cover
        return


def _ensure_source_item_columns() -> None:
    """Add traceability/quality columns to source_items if missing."""
    try:
        with engine.connect() as conn:
            columns = conn.execute(text("PRAGMA table_info(source_items)")).fetchall()
            column_names = {row[1] for row in columns}

            additions = [
                ("source_row_id", "TEXT"),
                ("source_row_number", "INTEGER"),
                ("source_ref", "TEXT"),
                ("content_hash", "TEXT"),
                ("is_composite", "INTEGER NOT NULL DEFAULT 0"),
                ("cas_numbers_json", "TEXT NOT NULL DEFAULT '[]'"),
            ]
            for name, col_type in additions:
                if name in column_names:
                    continue
                conn.execute(text(f"ALTER TABLE source_items ADD COLUMN {name} {col_type}"))
                LOGGER.info("Added %s column to source_items", name)
    except Exception:  # pragma: no cover
        return


def _ensure_source_catalog_indexes() -> None:
    """Best-effort indexing for source_catalog_items (SQLite-safe)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_catalog_cas ON source_catalog_items(cas_number)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_catalog_ec ON source_catalog_items(ec_number)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_catalog_inci ON source_catalog_items(inci_name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_source_catalog_common ON source_catalog_items(common_name)"))
    except Exception:  # pragma: no cover
        return


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
            ("usage_leave_on_max", "TEXT"),
            ("usage_rinse_off_max", "TEXT"),
            ("approved", "INTEGER NOT NULL DEFAULT 1"),
            ("status", "TEXT NOT NULL DEFAULT 'active'"),
            ("needs_review_reason", "TEXT"),
        ]

        for name, col_type in additions:
            if name in column_names:
                continue
            conn.execute(text(f"ALTER TABLE ingredient_items ADD COLUMN {name} {col_type}"))
            LOGGER.info("Added %s column to ingredient_items", name)


def _ensure_ingredient_columns() -> None:
    """Add SOP-required columns to ingredients if missing."""
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(ingredients)")).fetchall()
        column_names = {row[1] for row in columns}
        additions = [
            ("ingredient_category", "TEXT"),
            ("origin", "TEXT"),
            ("refinement_level", "TEXT"),
            ("derived_from", "TEXT"),
            ("usage_restrictions", "TEXT"),
            ("prohibited_flag", "INTEGER NOT NULL DEFAULT 0"),
            ("gras_status", "INTEGER NOT NULL DEFAULT 0"),
            ("ifra_category", "TEXT"),
            ("allergen_flag", "INTEGER NOT NULL DEFAULT 0"),
            ("colorant_flag", "INTEGER NOT NULL DEFAULT 0"),
        ]
        for name, col_type in additions:
            if name in column_names:
                continue
            conn.execute(text(f"ALTER TABLE ingredients ADD COLUMN {name} {col_type}"))
            LOGGER.info("Added %s column to ingredients", name)


def _seed_taxonomy_tables() -> None:
    """Seed curated taxonomy lookup tables (idempotent)."""
    try:
        with get_session() as session:
            # Ingredient categories
            existing = {r[0] for r in session.query(IngredientCategoryTerm.name).all()}
            for name in INGREDIENT_CATEGORIES_PRIMARY:
                if name not in existing:
                    session.add(IngredientCategoryTerm(name=name))

            # Master categories
            existing = {r[0] for r in session.query(MasterCategoryTerm.name).all()}
            for name in MASTER_CATEGORIES:
                if name not in existing:
                    session.add(MasterCategoryTerm(name=name))

            # Refinement levels
            existing = {r[0] for r in session.query(RefinementLevelTerm.name).all()}
            for name in REFINEMENT_LEVELS:
                if name not in existing:
                    session.add(RefinementLevelTerm(name=name))

            # Physical forms
            existing = {r[0] for r in session.query(PhysicalFormTerm.name).all()}
            for name in PHYSICAL_FORMS:
                if name not in existing:
                    session.add(PhysicalFormTerm(name=name))

            # Variations
            existing = {r[0] for r in session.query(VariationTerm.name).all()}
            for name in VARIATIONS_CURATED:
                if name not in existing:
                    session.add(VariationTerm(name=name, approved=True))

            existing_rules = {
                (r.master_category, r.source_type, r.source_value)
                for r in session.query(MasterCategoryRule).all()
            }
            # Seed data-driven rules from curated constants.
            for mc, st, sv in MASTER_CATEGORY_RULE_SEED:
                key = (mc, st, sv)
                if key not in existing_rules and mc in MASTER_CATEGORIES:
                    session.add(MasterCategoryRule(master_category=mc, source_type=st, source_value=sv))
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.debug("Skipping taxonomy seeding: %s", exc)


def _ensure_normalized_term_columns() -> None:
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(normalized_terms)")).fetchall()
        column_names = {row[1] for row in columns}
        additions = [
            ("ingredient_category", "TEXT"),
            ("origin", "TEXT"),
            ("refinement_level", "TEXT"),
            ("derived_from", "TEXT"),
            ("ingredient_category_confidence", "INTEGER"),
            ("origin_confidence", "INTEGER"),
            ("refinement_confidence", "INTEGER"),
            ("derived_from_confidence", "INTEGER"),
            ("overall_confidence", "INTEGER"),
        ]
        for name, col_type in additions:
            if name in column_names:
                continue
            conn.execute(text(f"ALTER TABLE normalized_terms ADD COLUMN {name} {col_type}"))
            LOGGER.info("Added %s column to normalized_terms", name)


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
    raise RuntimeError("_derive_item_name signature changed; use _derive_item_display_name")


def _derive_item_display_name(
    *,
    base_term: str,
    variation: str,
    variation_bypass: bool,
    physical_form: str,
    form_bypass: bool,
) -> str:
    """SOP item name generation: base + (variation) + form suffix."""
    base_clean = (base_term or "").strip()
    if not base_clean:
        return ""
    name = base_clean

    var_clean = (variation or "").strip()
    if var_clean and not variation_bypass:
        name = f"{name} ({var_clean})"

    form_clean = (physical_form or "").strip()
    if form_clean and not form_bypass:
        # Avoid double-appending if already present (e.g., variation includes 'Essential Oil' and form is Oil).
        if form_clean.casefold() not in name.casefold():
            name = f"{name} {form_clean}"

    return name


def derive_item_display_name(
    *,
    base_term: str,
    variation: str,
    variation_bypass: bool,
    physical_form: str,
    form_bypass: bool,
) -> str:
    """Public wrapper for SOP item name generation (used by portal edits)."""
    return _derive_item_display_name(
        base_term=base_term,
        variation=variation,
        variation_bypass=variation_bypass,
        physical_form=physical_form,
        form_bypass=form_bypass,
    )


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


def get_random_term_for_initial(initial: str) -> Optional[str]:
    """Return a random queued term for the given initial (A..Z), or None if none exist."""
    ensure_tables_exist()
    letter = (initial or "").strip()[:1].upper()
    if not letter:
        return None
    with get_session() as session:
        row = (
            session.execute(
                select(TaskQueue.term)
                .where(TaskQueue.term.collate("NOCASE").like(f"{letter}%"))
                .order_by(func.random())
                .limit(1)
            )
            .first()
        )
        return row[0] if row else None


def get_next_term_for_initial_after(initial: str, start_after: str) -> Optional[str]:
    """Return the next queued term for `initial` strictly after `start_after` (NOCASE)."""
    ensure_tables_exist()
    letter = (initial or "").strip()[:1].upper()
    if not letter:
        return None
    after = (start_after or "").strip()
    with get_session() as session:
        row = (
            session.execute(
                select(TaskQueue.term)
                .where(
                    TaskQueue.term.collate("NOCASE").like(f"{letter}%"),
                    TaskQueue.term.collate("NOCASE") > after,
                )
                .order_by(TaskQueue.term.collate("NOCASE").asc(), TaskQueue.term.asc())
                .limit(1)
            )
            .first()
        )
        return row[0] if row else None


def get_next_missing_normalized_term_between(
    *,
    initial: str,
    start_after: str,
    end_before: str | None,
) -> Optional[dict[str, str]]:
    """Return the next normalized term (from curated sources) not yet queued, constrained to a gap.

    Args:
        initial: Letter bucket (A..Z)
        start_after: Lower bound (exclusive)
        end_before: Upper bound (exclusive). If None, treat as open-ended within the letter.
    """
    ensure_tables_exist()
    letter = (initial or "").strip()[:1].upper()
    if not letter:
        return None
    lower = (start_after or "").strip()
    upper = (end_before or "").strip() if end_before else None

    with get_session() as session:
        query = (
            select(NormalizedTerm.term, NormalizedTerm.seed_category)
            .where(
                NormalizedTerm.term.collate("NOCASE").like(f"{letter}%"),
                NormalizedTerm.term.collate("NOCASE") > lower,
            )
            .where(~exists(select(1).where(TaskQueue.term == NormalizedTerm.term)))
        )
        if upper:
            query = query.where(NormalizedTerm.term.collate("NOCASE") < upper)

        row = (
            session.execute(
                query.order_by(NormalizedTerm.term.collate("NOCASE").asc(), NormalizedTerm.term.asc()).limit(1)
            )
            .first()
        )
        if not row:
            return None
        term, seed_category = row
        return {"term": str(term), "seed_category": (str(seed_category) if seed_category else "")}


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
    ingredient_category_raw = (ingredient.get("ingredient_category") or "").strip() or None
    origin = _guess_origin(ingredient, cleaned)
    refinement_level = _coerce_refinement(ingredient.get("refinement_level"))
    ingredient_category = _coerce_primary_category(ingredient_category_raw, cleaned, cleaned_category)
    # Guardrail: don't allow invalid origin/category pairings.
    if ingredient_category and not _is_category_allowed_for_origin(origin, ingredient_category):
        if origin == "Synthetic":
            ingredient_category = "Synthetic - Other"
        elif origin == "Fermentation":
            ingredient_category = "Fermentation - Other"
        elif origin == "Marine-Derived":
            ingredient_category = "Marine - Other"
        elif origin in {"Animal-Derived", "Animal-Byproduct"}:
            ingredient_category = "Animal - Other"
        else:
            ingredient_category = ""
    refinement_level = _coerce_refinement_for_category(refinement_level, ingredient_category)
    derived_from = (ingredient.get("derived_from") or "").strip() or None
    usage_restrictions = ingredient.get("usage_restrictions")
    prohibited_flag = _coerce_bool(ingredient.get("prohibited_flag"), default=False)
    gras_status = _coerce_bool(ingredient.get("gras_status"), default=False)
    ifra_category = (ingredient.get("ifra_category") or "").strip() or None
    allergen_flag = _coerce_bool(ingredient.get("allergen_flag"), default=False)
    colorant_flag = _coerce_bool(ingredient.get("colorant_flag"), default=False)

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
        record.ingredient_category = ingredient_category
        record.origin = origin
        record.refinement_level = refinement_level
        record.derived_from = derived_from
        if isinstance(usage_restrictions, str):
            record.usage_restrictions = usage_restrictions.strip()
        record.prohibited_flag = prohibited_flag
        record.gras_status = gras_status
        record.ifra_category = ifra_category
        record.allergen_flag = allergen_flag
        record.colorant_flag = colorant_flag
        if isinstance(short_description, str):
            record.short_description = short_description.strip()
        if isinstance(detailed_description, str):
            record.detailed_description = detailed_description.strip()
        record.payload_json = payload_json
        record.compiled_at = datetime.utcnow()

        # Replace items + item values + ingredient master categories (deterministic).
        existing_item_ids = [
            r[0]
            for r in session.query(IngredientItemRecord.id)
            .filter(IngredientItemRecord.ingredient_term == cleaned)
            .all()
        ]
        if existing_item_ids:
            session.query(IngredientItemValue).filter(IngredientItemValue.item_id.in_(existing_item_ids)).delete(synchronize_session=False)
        session.query(IngredientItemRecord).filter(IngredientItemRecord.ingredient_term == cleaned).delete()
        session.query(IngredientMasterCategory).filter(IngredientMasterCategory.ingredient_term == cleaned).delete()

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
            # Enforce curated physical forms (otherwise keep empty for review).
            if physical_form and physical_form not in PHYSICAL_FORMS:
                physical_form = ""

            # Track/approve variation vocabulary.
            if variation:
                existing_var = session.get(VariationTerm, variation)
                if existing_var is None:
                    session.add(VariationTerm(name=variation, approved=(variation in VARIATIONS_CURATED)))
            form_bypass = _coerce_bool(raw_item.get("form_bypass"), default=False)
            variation_bypass = _coerce_bool(raw_item.get("variation_bypass"), default=False)

            derived_item_name = _derive_item_display_name(
                base_term=cleaned,
                variation=variation,
                variation_bypass=variation_bypass,
                physical_form=physical_form,
                form_bypass=form_bypass,
            )
            if not derived_item_name:
                continue

            cleaned_item = dict(raw_item)
            cleaned_item["variation"] = variation
            cleaned_item["physical_form"] = physical_form
            cleaned_item["item_name"] = derived_item_name
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
            usage = specs.get("usage_rate_percent") if isinstance(specs.get("usage_rate_percent"), dict) else {}

            # Quarantine: keep compiled data, but require approval if variation isn't approved or form is missing.
            approved = True
            status = "active"
            reasons: list[str] = []
            if variation:
                vrow = session.get(VariationTerm, variation)
                if vrow is not None and not bool(vrow.approved):
                    approved = False
                    status = "quarantine"
                    reasons.append(f"Unapproved variation: {variation}")
            if not physical_form:
                approved = False
                status = "quarantine"
                reasons.append("Missing/invalid physical_form")

            item_row = IngredientItemRecord(
                ingredient_term=cleaned,
                item_name=derived_item_name,
                variation=variation,
                physical_form=physical_form,
                form_bypass=form_bypass,
                variation_bypass=variation_bypass,
                approved=approved,
                status=status,
                needs_review_reason="; ".join(reasons) if reasons else None,
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
                usage_leave_on_max=str(usage.get("leave_on_max")) if usage.get("leave_on_max") not in (None, "") else None,
                usage_rinse_off_max=str(usage.get("rinse_off_max")) if usage.get("rinse_off_max") not in (None, "") else None,
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
            # SOP: applications must have at least 1. If missing, store Unknown.
            applications = cleaned_item.get("applications")
            if not applications:
                applications = ["Unknown"]
                cleaned_item["applications"] = applications
            _add_values("applications", applications)
            _add_values("function_tags", cleaned_item.get("function_tags"))
            _add_values("safety_tags", cleaned_item.get("safety_tags"))
            _add_values("sds_hazards", cleaned_item.get("sds_hazards"))

            sourcing = cleaned_item.get("sourcing") if isinstance(cleaned_item.get("sourcing"), dict) else {}
            _add_values("certifications", sourcing.get("certifications"))
            _add_values("common_origins", sourcing.get("common_origins"))
            _add_values("supply_risks", sourcing.get("supply_risks"))

        # Derive and persist ingredient master categories (UX group).
        for mc in _derive_master_categories_from_rules(session, ingredient_category=ingredient_category, items=items):
            session.add(IngredientMasterCategory(ingredient_term=cleaned, master_category=mc))


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
            record.ingredient_category = (row.get("ingredient_category") or "").strip() or None
            record.origin = (row.get("origin") or "").strip() or None
            record.refinement_level = (row.get("refinement_level") or "").strip() or None
            record.derived_from = (row.get("derived_from") or "").strip() or None
            for key in (
                "ingredient_category_confidence",
                "origin_confidence",
                "refinement_confidence",
                "derived_from_confidence",
                "overall_confidence",
            ):
                val = row.get(key)
                try:
                    setattr(record, key, int(val) if val is not None and str(val).strip() != "" else None)
                except Exception:
                    setattr(record, key, None)
            sources_json = row.get("sources_json")
            if isinstance(sources_json, str) and sources_json.strip():
                record.sources_json = sources_json
            record.normalized_at = datetime.utcnow()
    return inserted


def get_normalized_term(term: str) -> Optional[dict[str, Any]]:
    """Fetch normalized term record as a dict for compiler prefill."""
    ensure_tables_exist()
    cleaned = (term or "").strip()
    if not cleaned:
        return None
    with get_session() as session:
        row: Optional[NormalizedTerm] = session.get(NormalizedTerm, cleaned)
        if row is None:
            return None
        return {
            "term": row.term,
            "seed_category": row.seed_category,
            "ingredient_category": row.ingredient_category,
            "origin": row.origin,
            "refinement_level": row.refinement_level,
            "derived_from": row.derived_from,
            "botanical_name": row.botanical_name,
            "inci_name": row.inci_name,
            "cas_number": row.cas_number,
            "description": row.description,
            "ingredient_category_confidence": row.ingredient_category_confidence,
            "origin_confidence": row.origin_confidence,
            "refinement_confidence": row.refinement_confidence,
            "derived_from_confidence": row.derived_from_confidence,
            "overall_confidence": row.overall_confidence,
            "sources_json": row.sources_json,
        }


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


def upsert_source_items(rows: Iterable[dict[str, Any]]) -> int:
    """Upsert source item rows (INCI/TGSC) into source_items. Returns newly inserted count."""
    ensure_tables_exist()
    inserted = 0
    with get_session() as session:
        existing = {r[0] for r in session.query(SourceItem.key).all()}
        for row in rows:
            key = (row.get("key") or "").strip()
            if not key or key in existing:
                continue
            raw_name = (row.get("raw_name") or "").strip()
            if not raw_name:
                continue
            status = (row.get("status") or "linked").strip().lower()
            if status not in {"linked", "orphan", "review"}:
                status = "review"
            item = SourceItem(
                key=key,
                source=(row.get("source") or "").strip() or "unknown",
                source_row_id=(row.get("source_row_id") or "").strip() or None,
                source_row_number=row.get("source_row_number"),
                source_ref=(row.get("source_ref") or "").strip() or None,
                content_hash=(row.get("content_hash") or "").strip() or None,
                is_composite=bool(row.get("is_composite")) if row.get("is_composite") is not None else False,
                raw_name=raw_name,
                inci_name=(row.get("inci_name") or "").strip() or None,
                cas_number=(row.get("cas_number") or "").strip() or None,
                cas_numbers_json=(row.get("cas_numbers_json") or "[]"),
                derived_term=(row.get("derived_term") or "").strip() or None,
                derived_variation=(row.get("derived_variation") or "").strip() or None,
                derived_physical_form=(row.get("derived_physical_form") or "").strip() or None,
                origin=(row.get("origin") or "").strip() or None,
                ingredient_category=(row.get("ingredient_category") or "").strip() or None,
                refinement_level=(row.get("refinement_level") or "").strip() or None,
                status=status,
                needs_review_reason=(row.get("needs_review_reason") or "").strip() or None,
                payload_json=(row.get("payload_json") or "{}"),
                ingested_at=datetime.utcnow(),
            )
            session.add(item)
            existing.add(key)
            inserted += 1
    return inserted


def get_source_item_summary() -> dict[str, int]:
    """Return counts for source item ingestion statuses."""
    ensure_tables_exist()
    out: dict[str, int] = {"linked": 0, "orphan": 0, "review": 0, "total": 0}
    with get_session() as session:
        rows = session.query(SourceItem.status, func.count(SourceItem.key)).group_by(SourceItem.status).all()
        for status, count in rows:
            s = (status or "").strip().lower()
            if s not in out:
                out[s] = 0
            out[s] = int(count or 0)
    out["total"] = sum(v for k, v in out.items() if k != "total")
    return out
