"""Iterative orchestrator that builds the ingredient library one record at a time."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Set
from sqlalchemy import func

# Thread-local storage for worker stats
_worker_stats = threading.local()
DEFAULT_WORKERS = int(os.getenv("COMPILER_WORKERS", "1"))


class AtomicCounter:
    """Thread-safe counter for tracking compilation order across workers."""
    def __init__(self, start: int = 0):
        self._value = start
        self._lock = threading.Lock()
    
    def increment(self) -> int:
        """Increment and return the new value (atomically)."""
        with self._lock:
            self._value += 1
            return self._value
    
    @property
    def value(self) -> int:
        with self._lock:
            return self._value

try:  # pragma: no cover - fallback for direct script execution
    from . import ai_worker, database_manager
except ImportError:  # pragma: no cover
    import ai_worker  # type: ignore
    import database_manager  # type: ignore

LOGGER = logging.getLogger("data_builder.ingredients.compiler")
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
INGREDIENT_DIR = OUTPUT_DIR / "ingredients"
PHYSICAL_FORMS_FILE = OUTPUT_DIR / "physical_forms.json"
VARIATIONS_FILE = OUTPUT_DIR / "variations.json"
TAXONOMY_FILE = OUTPUT_DIR / "taxonomies.json"
DEFAULT_SLEEP_SECONDS = float(os.getenv("COMPILER_SLEEP_SECONDS", "3"))
WRITE_INGREDIENT_FILES = os.getenv("COMPILER_WRITE_INGREDIENT_FILES", "0").strip() in {"1", "true", "True"}

DEFAULT_CLUSTER_LIMIT = int(os.getenv("CLUSTER_COMPILER_LIMIT", "50"))


def slugify(value: str) -> str:
    """Generate a filesystem-safe slug."""

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.lower()).strip("_")
    return slug or "ingredient"


def ensure_output_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INGREDIENT_DIR.mkdir(parents=True, exist_ok=True)


def _load_json_list(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {str(item) for item in data if str(item).strip()}
    except json.JSONDecodeError:
        LOGGER.warning("Failed to parse %s; regenerating.", path)
    return set()


def _write_json_list(path: Path, values: Iterable[str]) -> None:
    sorted_values = sorted({value for value in values if value})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted_values, indent=2), encoding="utf-8")


def _load_taxonomy_map() -> MutableMapping[str, Set[str]]:
    if not TAXONOMY_FILE.exists():
        return {}
    try:
        data = json.loads(TAXONOMY_FILE.read_text(encoding="utf-8"))
        return {key: set(value) for key, value in data.items() if isinstance(value, list)}
    except json.JSONDecodeError:
        LOGGER.warning("Failed to parse %s; regenerating.", TAXONOMY_FILE)
        return {}


def _write_taxonomy_map(values: MutableMapping[str, Set[str]]) -> None:
    serialized = {key: sorted(list(val_set)) for key, val_set in values.items() if val_set}
    TAXONOMY_FILE.parent.mkdir(parents=True, exist_ok=True)
    TAXONOMY_FILE.write_text(json.dumps(serialized, indent=2), encoding="utf-8")


SPEC_FIELD_MAPPING = {
    "density": "density_g_ml",
    "flash_point": "flash_point_celsius",
    "melting_point": "melting_point_celsius",
    "boiling_point": "boiling_point_celsius",
    "iodine": "iodine_value",
    "sap_naoh": "sap_naoh",
    "sap_koh": "sap_koh",
    "molecular_weight": "molecular_weight",
    "molecular_formula": "molecular_formula",
    "refractive_index": "refractive_index",
    "viscosity": "viscosity_cps",
    "ph": "ph_range",
}


def _normalize_specs_for_ai(specs: Dict[str, Any]) -> Dict[str, Any]:
    """Map source spec field names to schema-expected names for AI context."""
    if not specs:
        return {}
    normalized = {}
    for key, val in specs.items():
        if key == "pubchem":
            normalized[key] = val
            continue
        mapped_key = SPEC_FIELD_MAPPING.get(key, key)
        if val is not None and val != "" and val != "Not Found":
            normalized[mapped_key] = val
    return normalized


def validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Guard against malformed AI responses."""

    ingredient = payload.get("ingredient")
    if not isinstance(ingredient, dict):
        raise ValueError("Payload missing top-level 'ingredient' object")

    common_name = ingredient.get("common_name")
    if not common_name or not isinstance(common_name, str):
        raise ValueError("Ingredient is missing a valid 'common_name'")

    items = ingredient.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("Ingredient must include at least one item form")

    return ingredient


def update_lookup_files(payload: Dict[str, Any]) -> None:
    """Refresh the supporting lookup files for physical forms, variations, and taxonomies."""

    ingredient = payload.get("ingredient", {})
    items: List[Dict[str, Any]] = ingredient.get("items", []) or []

    # Physical forms
    existing_forms = _load_json_list(PHYSICAL_FORMS_FILE)
    for item in items:
        form = item.get("physical_form")
        if isinstance(form, str) and form.strip():
            existing_forms.add(form.strip())
    _write_json_list(PHYSICAL_FORMS_FILE, existing_forms)

    # Variations (separate from physical_form)
    existing_variations = _load_json_list(VARIATIONS_FILE)
    for item in items:
        variation = item.get("variation")
        if isinstance(variation, str) and variation.strip():
            existing_variations.add(variation.strip())
    _write_json_list(VARIATIONS_FILE, existing_variations)

    taxonomy_values = _load_taxonomy_map()

    def _coerce_str_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [v for v in value if isinstance(v, str)]
        if isinstance(value, str):
            return [value]
        return []

    def _extend_taxonomy(key: str, values: Any) -> None:
        bucket = taxonomy_values.setdefault(key, set())
        for value in _coerce_str_list(values):
            if isinstance(value, str) and value.strip():
                bucket.add(value.strip())

    # Item level tags
    for item in items:
        _extend_taxonomy("function_tags", item.get("function_tags"))
        _extend_taxonomy("applications", item.get("applications"))
        _extend_taxonomy("safety_tags", item.get("safety_tags"))

    # Top-level taxonomy dictionary if present
    taxonomy_obj = ingredient.get("taxonomy", {}) or {}
    for key, values in taxonomy_obj.items():
        _extend_taxonomy(key, values)

    _write_taxonomy_map(taxonomy_values)


def save_payload(payload: Dict[str, Any], slug: str) -> Path:
    target = INGREDIENT_DIR / f"{slug}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _safe_json_list(text: str | None) -> list[Any]:
    try:
        val = json.loads(text or "[]")
        return val if isinstance(val, list) else []
    except Exception:
        return []


def _safe_json_dict(text: str | None) -> dict[str, Any]:
    try:
        val = json.loads(text or "{}")
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def _cluster_term_from_id(cluster_id: str) -> str:
    cid = (cluster_id or "").strip()
    if cid.startswith("term:"):
        return cid[len("term:") :].strip()
    return ""


def _extract_stage1_field(field_data: Any) -> str | None:
    """Extract value from stage-1 field wrapper or return plain value."""
    if isinstance(field_data, dict) and "value" in field_data:
        status = field_data.get("status", "")
        if status in ("found", ""):
            return _clean(field_data.get("value"))
        return None
    return _clean(field_data) or None


def _find_ingredient_by_terms(session: Any, terms: Iterable[str]) -> database_manager.IngredientRecord | None:
    cleaned = [t.strip() for t in terms if isinstance(t, str) and t.strip()]
    if not cleaned:
        return None
    lowered = {t.lower() for t in cleaned}
    rows = (
        session.query(database_manager.IngredientRecord)
        .filter(func.lower(database_manager.IngredientRecord.term).in_(lowered))
        .all()
    )
    if not rows:
        return None
    for term in cleaned:
        for row in rows:
            if row.term == term:
                return row
    return rows[0]


def _stage1_core_from_ingredient(record: database_manager.IngredientRecord) -> dict[str, Any]:
    return {
        "origin": getattr(record, "origin", None),
        "ingredient_category": getattr(record, "ingredient_category", None),
        "refinement_level": getattr(record, "refinement_level", None),
        "derived_from": getattr(record, "derived_from", None),
        "category": getattr(record, "category", None),
        "botanical_name": getattr(record, "botanical_name", None),
        "inci_name": getattr(record, "inci_name", None),
        "cas_number": getattr(record, "cas_number", None),
        "short_description": getattr(record, "short_description", None),
        "detailed_description": getattr(record, "detailed_description", None),
    }


def _item_identity_key(payload: dict[str, Any]) -> tuple[str, str]:
    variation = _clean(payload.get("variation") or "").lower()
    physical_form = _clean(payload.get("physical_form") or "").lower()
    return variation, physical_form


def _stage1_snapshot(rec: database_manager.CompiledClusterRecord) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    payload = _safe_json_dict(getattr(rec, "payload_json", None))
    stage1 = payload.get("stage1") if isinstance(payload.get("stage1"), dict) else {}
    core = stage1.get("ingredient_core") if isinstance(stage1.get("ingredient_core"), dict) else {}
    dq = stage1.get("data_quality") if isinstance(stage1.get("data_quality"), dict) else {}
    common_name = stage1.get("common_name") if isinstance(stage1.get("common_name"), str) else None
    return core, dq, common_name


def _build_cluster_core(rec: database_manager.CompiledClusterRecord) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    core_raw, dq, common_name = _stage1_snapshot(rec)
    ingredient_core = {
        "origin": _extract_stage1_field(core_raw.get("origin")) or getattr(rec, "origin", None),
        "ingredient_category": _extract_stage1_field(core_raw.get("ingredient_category")) or getattr(rec, "ingredient_category", None),
        "refinement_level": _extract_stage1_field(core_raw.get("base_refinement"))
        or _extract_stage1_field(core_raw.get("refinement_level"))
        or getattr(rec, "refinement_level", None),
        "derived_from": _extract_stage1_field(core_raw.get("derived_from")) or getattr(rec, "derived_from", None),
        "category": _extract_stage1_field(core_raw.get("category"))
        or _extract_stage1_field(core_raw.get("ingredient_category"))
        or getattr(rec, "ingredient_category", None),
        "botanical_name": _extract_stage1_field(core_raw.get("botanical_name")) or getattr(rec, "botanical_name", None),
        "inci_name": _extract_stage1_field(core_raw.get("inci_name")) or getattr(rec, "inci_name", None),
        "cas_number": _extract_stage1_field(core_raw.get("cas_number")) or getattr(rec, "cas_number", None),
        "short_description": _extract_stage1_field(core_raw.get("short_description")),
        "detailed_description": _extract_stage1_field(core_raw.get("detailed_description")),
    }
    return ingredient_core, dq, common_name


def _backfill_cluster_items_from_ingredient(
    session: Any, cluster_id: str, ingredient: database_manager.IngredientRecord
) -> int:
    payload = _safe_json_dict(getattr(ingredient, "payload_json", None))
    ingredient_blob = payload.get("ingredient") if isinstance(payload.get("ingredient"), dict) else {}
    items = ingredient_blob.get("items") if isinstance(ingredient_blob.get("items"), list) else []
    items_by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            continue
        items_by_key[_item_identity_key(item)].append(item)

    rows = (
        session.query(database_manager.CompiledClusterItemRecord)
        .filter(database_manager.CompiledClusterItemRecord.cluster_id == cluster_id)
        .filter(database_manager.CompiledClusterItemRecord.item_status != "done")
        .order_by(database_manager.CompiledClusterItemRecord.merged_item_form_id.asc())
        .all()
    )
    updated = 0
    now = datetime.now(timezone.utc)
    compiled_at = getattr(ingredient, "compiled_at", None) or now
    for row in rows:
        key = (
            _clean(getattr(row, "derived_variation", "")).lower(),
            _clean(getattr(row, "derived_physical_form", "")).lower(),
        )
        candidates = items_by_key.get(key) or []
        if not candidates:
            continue
        item_payload = candidates.pop(0)
        row.item_json = json.dumps(item_payload, ensure_ascii=False, sort_keys=True)
        row.item_status = "done"
        row.item_compiled_at = compiled_at
        row.item_error = None
        row.updated_at = now
        updated += 1
    return updated


def _assemble_cluster_payload(
    *,
    term: str,
    rec: database_manager.CompiledClusterRecord,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    ingredient_core, dq, common_name = _build_cluster_core(rec)
    ingredient: dict[str, Any] = dict(ingredient_core)
    ingredient["common_name"] = common_name if common_name else term
    ingredient["items"] = items
    if "documentation" not in ingredient:
        ingredient["documentation"] = {"references": [], "last_verified": None}
    confidence = dq.get("confidence") if isinstance(dq, dict) else None
    caveats = dq.get("caveats") if isinstance(dq, dict) else []
    if not isinstance(confidence, (int, float)):
        confidence = 0.7
    caveats = caveats if isinstance(caveats, list) else []
    return {
        "ingredient": ingredient,
        "data_quality": {"confidence": float(confidence), "caveats": caveats},
    }


def _finalize_cluster_if_complete(cluster_id: str) -> bool:
    """Persist a compiled ingredient when all cluster items are done."""
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        rec = session.get(database_manager.CompiledClusterRecord, cluster_id)
        if rec is None:
            return False
        term = _clean(getattr(rec, "compiled_term", None)) or _clean(getattr(rec, "raw_canonical_term", None)) or _cluster_term_from_id(cluster_id) or cluster_id
        if not term:
            return False
        if _find_ingredient_by_terms(session, [term]) is not None:
            return True
        pending = (
            session.query(database_manager.CompiledClusterItemRecord)
            .filter(database_manager.CompiledClusterItemRecord.cluster_id == cluster_id)
            .filter(database_manager.CompiledClusterItemRecord.item_status != "done")
            .first()
        )
        if pending is not None:
            return False
        item_rows = (
            session.query(database_manager.CompiledClusterItemRecord)
            .filter(database_manager.CompiledClusterItemRecord.cluster_id == cluster_id)
            .order_by(database_manager.CompiledClusterItemRecord.merged_item_form_id.asc())
            .all()
        )
        items: list[dict[str, Any]] = []
        for row in item_rows:
            payload = _safe_json_dict(getattr(row, "item_json", None))
            if isinstance(payload, dict) and payload:
                items.append(payload)
    payload = _assemble_cluster_payload(term=term, rec=rec, items=items)
    ingredient_core = dict(payload.get("ingredient") or {})
    ingredient_core.pop("items", None)
    ingredient_core.pop("taxonomy", None)
    try:
        taxonomy_payload = ai_worker.compile_taxonomy(term, ingredient_core=ingredient_core, items=items)
        taxonomy = taxonomy_payload.get("taxonomy") if isinstance(taxonomy_payload.get("taxonomy"), dict) else {}
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.warning("Stage 2 taxonomy failed for %s: %s", term, exc)
        taxonomy = {}
    payload["ingredient"]["taxonomy"] = taxonomy
    database_manager.upsert_compiled_ingredient(
        term,
        payload,
        seed_category=getattr(rec, "seed_category", None),
        priority=getattr(rec, "priority", None),
    )
    if WRITE_INGREDIENT_FILES:
        slug = slugify(term)
        save_payload(payload, slug)
    update_lookup_files(payload)
    return True


def _select_stage1_cluster_ids(*, limit: int | None, cluster_id: str | None) -> list[str]:
    """Select clusters whose term is not yet normalized/compiled (Stage 1 pending)."""
    database_manager.ensure_tables_exist()
    cid = (cluster_id or "").strip() or None
    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceDefinition.cluster_id).outerjoin(
            database_manager.CompiledClusterRecord,
            database_manager.CompiledClusterRecord.cluster_id == database_manager.SourceDefinition.cluster_id,
        )
        q = q.filter(database_manager.SourceDefinition.cluster_id.isnot(None))
        if cid:
            q = q.filter(database_manager.SourceDefinition.cluster_id == cid)
        q = q.filter(
            (database_manager.CompiledClusterRecord.cluster_id.is_(None))
            | (database_manager.CompiledClusterRecord.term_status != "done")
        )
        q = q.order_by(database_manager.SourceDefinition.cluster_id.asc())
        ids = [str(r[0]) for r in q.all() if r and r[0]]
        if not ids:
            return []
    priority_map = database_manager.build_cluster_priority_map()
    ids.sort(
        key=lambda cluster_id: (
            -int(priority_map.get(cluster_id, database_manager.DEFAULT_PRIORITY)),
            cluster_id,
        )
    )
    if limit:
        ids = ids[: int(limit)]
    return ids


def _select_stage2_cluster_ids(*, limit: int | None, cluster_id: str | None) -> list[str]:
    """Select clusters whose term is compiled but have pending items (Stage 2 pending)."""
    database_manager.ensure_tables_exist()
    cid = (cluster_id or "").strip() or None
    with database_manager.get_session() as session:
        q = (
            session.query(
                database_manager.CompiledClusterRecord.cluster_id,
                database_manager.CompiledClusterRecord.priority,
            )
            .join(
                database_manager.CompiledClusterItemRecord,
                database_manager.CompiledClusterItemRecord.cluster_id == database_manager.CompiledClusterRecord.cluster_id,
            )
            .filter(database_manager.CompiledClusterRecord.term_status == "done")
            .filter(database_manager.CompiledClusterItemRecord.item_status != "done")
        )
        if cid:
            q = q.filter(database_manager.CompiledClusterRecord.cluster_id == cid)
        rows = q.distinct().all()
    if not rows:
        return []
    priority_map = database_manager.build_cluster_priority_map()
    ordered = sorted(
        rows,
        key=lambda row: (
            -int(
                row[1]
                if row[1] is not None
                else priority_map.get(str(row[0]), database_manager.DEFAULT_PRIORITY)
            ),
            str(row[0]),
        ),
    )
    ids = [str(row[0]) for row in ordered if row and row[0]]
    if limit:
        ids = ids[: int(limit)]
    return ids


def _mirror_cluster_into_compiled(cluster_id: str) -> None:
    """Ensure compiled mirror rows exist for cluster + its merged_item_forms."""
    database_manager.ensure_tables_exist()
    cid = (cluster_id or "").strip()
    if not cid:
        return

    with database_manager.get_session() as session:
        raw_def = session.get(database_manager.SourceDefinition, cid)
        if raw_def is None:
            raise LookupError(f"Missing source_definitions cluster: {cid}")

        rec = session.get(database_manager.CompiledClusterRecord, cid)
        if rec is None:
            rec = database_manager.CompiledClusterRecord(cluster_id=cid)
            session.add(rec)

        rec.raw_canonical_term = getattr(raw_def, "canonical_term", None)
        rec.raw_reason = getattr(raw_def, "reason", None)
        rec.raw_origin = getattr(raw_def, "origin", None)
        rec.raw_ingredient_category = getattr(raw_def, "ingredient_category", None)
        rec.updated_at = datetime.now(timezone.utc)

        # Distinct merged items in this cluster (definition_cluster_id ties source_items -> merged_item_forms)
        mif_rows = (
            session.query(database_manager.MergedItemForm)
            .join(database_manager.SourceItem, database_manager.SourceItem.merged_item_id == database_manager.MergedItemForm.id)
            .filter(database_manager.SourceItem.definition_cluster_id == cid)
            .distinct()
            .order_by(database_manager.MergedItemForm.id.asc())
            .all()
        )

        for mif in mif_rows:
            existing = (
                session.query(database_manager.CompiledClusterItemRecord)
                .filter(database_manager.CompiledClusterItemRecord.cluster_id == cid)
                .filter(database_manager.CompiledClusterItemRecord.merged_item_form_id == int(mif.id))
                .first()
            )
            if existing is not None:
                continue

            raw_item = {
                "merged_item_form_id": int(mif.id),
                "derived_term": getattr(mif, "derived_term", None),
                "derived_variation": getattr(mif, "derived_variation", "") or "",
                "derived_physical_form": getattr(mif, "derived_physical_form", "") or "",
                "derived_parts": _safe_json_list(getattr(mif, "derived_parts_json", None)),
                "cas_numbers": _safe_json_list(getattr(mif, "cas_numbers_json", None)),
                "sources": _safe_json_dict(getattr(mif, "sources_json", None)),
                "merged_specs": _normalize_specs_for_ai(_safe_json_dict(getattr(mif, "merged_specs_json", None))),
                "merged_specs_sources": _safe_json_dict(getattr(mif, "merged_specs_sources_json", None)),
                "source_row_count": int(getattr(mif, "source_row_count", 0) or 0),
                "has_cosing": bool(getattr(mif, "has_cosing", False)),
                "has_tgsc": bool(getattr(mif, "has_tgsc", False)),
                "has_seed": bool(getattr(mif, "has_seed", False)),
            }
            session.add(
                database_manager.CompiledClusterItemRecord(
                    cluster_id=cid,
                    merged_item_form_id=int(mif.id),
                    derived_term=getattr(mif, "derived_term", None),
                    derived_variation=getattr(mif, "derived_variation", "") or "",
                    derived_physical_form=getattr(mif, "derived_physical_form", "") or "",
                    raw_item_json=json.dumps(raw_item, ensure_ascii=False, sort_keys=True),
                    item_json="{}",
                )
            )


def _build_cluster_context(cluster_id: str) -> dict[str, Any]:
    database_manager.ensure_tables_exist()
    cid = (cluster_id or "").strip()
    with database_manager.get_session() as session:
        raw_def = session.get(database_manager.SourceDefinition, cid)
        if raw_def is None:
            raise LookupError(f"Missing source_definitions cluster: {cid}")

        # Small sample of raw source rows for evidence.
        src_rows = (
            session.query(database_manager.SourceItem)
            .filter(database_manager.SourceItem.definition_cluster_id == cid)
            .order_by(database_manager.SourceItem.source.asc(), database_manager.SourceItem.raw_name.asc())
            .limit(25)
            .all()
        )
        src_samples = []
        for r in src_rows:
            src_samples.append(
                {
                    "source": getattr(r, "source", None),
                    "raw_name": getattr(r, "raw_name", None),
                    "inci_name": getattr(r, "inci_name", None),
                    "cas_number": getattr(r, "cas_number", None),
                    "derived_term": getattr(r, "derived_term", None),
                    "derived_variation": getattr(r, "derived_variation", None),
                    "derived_physical_form": getattr(r, "derived_physical_form", None),
                }
            )

        mif_rows = (
            session.query(database_manager.MergedItemForm)
            .join(database_manager.SourceItem, database_manager.SourceItem.merged_item_id == database_manager.MergedItemForm.id)
            .filter(database_manager.SourceItem.definition_cluster_id == cid)
            .distinct()
            .order_by(database_manager.MergedItemForm.id.asc())
            .all()
        )
        merged_items = []
        for mif in mif_rows[:25]:
            merged_items.append(
                {
                    "id": int(mif.id),
                    "derived_term": getattr(mif, "derived_term", None),
                    "derived_variation": getattr(mif, "derived_variation", "") or "",
                    "derived_physical_form": getattr(mif, "derived_physical_form", "") or "",
                    "cas_numbers": _safe_json_list(getattr(mif, "cas_numbers_json", None)),
                    "merged_specs": _normalize_specs_for_ai(_safe_json_dict(getattr(mif, "merged_specs_json", None))),
                }
            )

        return {
            "cluster_id": cid,
            "raw_definition": {
                "canonical_term": getattr(raw_def, "canonical_term", None),
                "reconciled_term": getattr(raw_def, "reconciled_term", None),
                "reconciled_variation": getattr(raw_def, "reconciled_variation", None),
                "origin": getattr(raw_def, "origin", None),
                "ingredient_category": getattr(raw_def, "ingredient_category", None),
                "confidence": getattr(raw_def, "confidence", None),
                "reason": getattr(raw_def, "reason", None),
                "item_count": getattr(raw_def, "item_count", None),
                "member_cas": _safe_json_list(getattr(raw_def, "member_cas_json", None)),
                "member_inci_samples": _safe_json_list(getattr(raw_def, "member_inci_samples_json", None)),
            },
            "merged_items": merged_items,
            "source_item_samples": src_samples,
        }


def _process_stage1_cluster(
    cid: str,
    priority_map: dict[str, int],
    rank_counter: AtomicCounter,
    sleep_seconds: float,
) -> tuple[bool, str | None, str | None]:
    """Process a single cluster for Stage 1 (term normalization). Returns (success, term, error)."""
    try:
        _mirror_cluster_into_compiled(cid)
        priority = int(priority_map.get(cid, database_manager.DEFAULT_PRIORITY))
        with database_manager.get_session() as session:
            rec = session.get(database_manager.CompiledClusterRecord, cid)
            if rec is None:
                return (False, None, "Record not found")
            rec.priority = priority
            raw_def = session.get(database_manager.SourceDefinition, cid)

            candidate_terms = [
                _clean(getattr(rec, "compiled_term", None)),
                _clean(getattr(raw_def, "reconciled_term", None)) if raw_def is not None else "",
                _clean(getattr(raw_def, "canonical_term", None)) if raw_def is not None else "",
            ]
            derived_term = _cluster_term_from_id(cid)
            if derived_term:
                candidate_terms.append(derived_term)
            ingredient = _find_ingredient_by_terms(session, candidate_terms)
            if ingredient is not None:
                core = _stage1_core_from_ingredient(ingredient)
                now = datetime.now(timezone.utc)
                try:
                    ingredient.priority = int(priority)
                except (TypeError, ValueError):
                    ingredient.priority = ingredient.priority
                rec.compiled_term = ingredient.term
                rec.seed_category = (ingredient.seed_category or "").strip() or None
                rec.origin = core.get("origin") or rec.raw_origin
                rec.ingredient_category = core.get("ingredient_category") or rec.raw_ingredient_category
                rec.refinement_level = core.get("refinement_level") or None
                rec.derived_from = core.get("derived_from") or None
                rec.botanical_name = core.get("botanical_name") or None
                rec.inci_name = core.get("inci_name") or None
                rec.cas_number = core.get("cas_number") or None
                legacy_common = getattr(ingredient, "common_name", None) or ""
                botanical = core.get("botanical_name") or ""
                compiled = ingredient.term or ""
                if legacy_common.lower().strip() in (botanical.lower().strip(), compiled.lower().strip(), "") or botanical.lower().strip() == legacy_common.lower().strip():
                    try:
                        context = _build_cluster_context(cid)
                        ai_result = ai_worker.normalize_cluster_term(cid, context)
                        legacy_common = ai_result.get("common_name") or legacy_common or compiled
                    except Exception:
                        legacy_common = legacy_common or compiled
                rec.payload_json = json.dumps(
                    {
                        "stage1": {
                            "term": rec.compiled_term,
                            "common_name": legacy_common or rec.compiled_term,
                            "ingredient_core": core,
                            "data_quality": {"confidence": None, "caveats": []},
                            "seeded_from_legacy": True,
                        }
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                rec.term_status = "done"
                rec.term_compiled_at = getattr(ingredient, "compiled_at", None) or now
                rec.term_error = None
                rec.updated_at = now
                rank = rank_counter.increment()
                rec.compilation_rank = rank
                LOGGER.info("Stage 1 done: #%d | term=%s | common_name=%s | priority=%s (seeded)", rank, rec.compiled_term, legacy_common, priority)
                return (True, rec.compiled_term, None)

            rec.term_status = "processing"
            rec.term_error = None
            rec.updated_at = datetime.now(timezone.utc)

        context = _build_cluster_context(cid)
        result = ai_worker.normalize_cluster_term(cid, context)
        term = _clean(result.get("term"))
        core = result.get("ingredient_core") if isinstance(result.get("ingredient_core"), dict) else {}
        dq = result.get("data_quality") if isinstance(result.get("data_quality"), dict) else {}
        final_priority = None
        final_term = None
        final_common_name = None

        with database_manager.get_session() as session:
            rec = session.get(database_manager.CompiledClusterRecord, cid)
            if rec is None:
                return (False, None, "Record disappeared")
            rec.compiled_term = term or rec.raw_canonical_term or cid
            rec.origin = _extract_stage1_field(core.get("origin")) or rec.raw_origin
            rec.ingredient_category = _extract_stage1_field(core.get("ingredient_category")) or rec.raw_ingredient_category
            rec.refinement_level = _extract_stage1_field(core.get("base_refinement")) or _extract_stage1_field(core.get("refinement_level")) or None
            rec.derived_from = _extract_stage1_field(core.get("derived_from")) or None
            rec.botanical_name = _extract_stage1_field(core.get("botanical_name")) or None
            rec.inci_name = _extract_stage1_field(core.get("inci_name")) or None
            rec.cas_number = _extract_stage1_field(core.get("cas_number")) or None
            rec.seed_category = None
            ai_priority = result.get("maker_priority")
            if ai_priority is not None:
                try:
                    rec.priority = max(1, min(100, int(ai_priority)))
                except (TypeError, ValueError):
                    rec.priority = priority
            else:
                rec.priority = priority
            common_name = result.get("common_name") or rec.compiled_term
            rec.payload_json = json.dumps(
                {"stage1": {"term": rec.compiled_term, "common_name": common_name, "ingredient_core": core, "data_quality": dq}},
                ensure_ascii=False,
                sort_keys=True,
            )
            rec.term_status = "done"
            rec.term_compiled_at = datetime.now(timezone.utc)
            rec.term_error = None
            rec.updated_at = datetime.now(timezone.utc)
            rank = rank_counter.increment()
            rec.compilation_rank = rank
            final_priority = rec.priority
            final_term = rec.compiled_term
            final_common_name = common_name
        if final_term and final_priority is not None:
            with database_manager.get_session() as session:
                tq = session.query(database_manager.TaskQueue).filter(
                    database_manager.TaskQueue.term == final_term
                ).first()
                if tq is not None:
                    tq.priority = final_priority
        LOGGER.info("Stage 1 done: #%d | term=%s | common_name=%s | priority=%s", rank, final_term, final_common_name, final_priority)
        return (True, final_term, None)
    except Exception as exc:
        with database_manager.get_session() as session:
            rec = session.get(database_manager.CompiledClusterRecord, cid)
            if rec is not None:
                rec.term_status = "error"
                rec.term_error = str(exc)
                rec.updated_at = datetime.now(timezone.utc)
        LOGGER.exception("Stage 1 failed for cluster %s: %s", cid, exc)
        return (False, None, str(exc))
    finally:
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))


def run_stage1_term_completion(*, cluster_id: str | None, limit: int | None, sleep_seconds: float, workers: int = 1) -> None:
    """Stage 1: complete + normalize the term for each raw cluster."""
    ids = _select_stage1_cluster_ids(limit=limit, cluster_id=cluster_id)
    if not ids:
        LOGGER.info("Stage 1: no clusters pending term completion.")
        return
    priority_map = database_manager.build_cluster_priority_map()
    with database_manager.get_session() as session:
        done_count = session.query(database_manager.CompiledClusterRecord).filter(
            database_manager.CompiledClusterRecord.term_status == "done"
        ).count()
    
    # Create atomic counter starting at done_count so ranks continue from where we left off
    rank_counter = AtomicCounter(start=done_count)
    
    workers = max(1, min(workers, 10))  # Cap at 10 workers
    LOGGER.info("Stage 1: processing %d clusters with %d worker(s), starting from rank %d", len(ids), workers, done_count + 1)
    
    if workers == 1:
        # Sequential processing (original behavior)
        ok = 0
        for cid in ids:
            success, term, error = _process_stage1_cluster(cid, priority_map, rank_counter, sleep_seconds)
            if success:
                ok += 1
        LOGGER.info("Stage 1 finished: ok=%s total=%s", ok, len(ids))
        return
    
    # Parallel processing with multiple workers
    ok = 0
    lock = threading.Lock()
    
    def worker_task(cid: str) -> tuple[bool, str | None, str | None]:
        return _process_stage1_cluster(cid, priority_map, rank_counter, sleep_seconds)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(worker_task, cid): cid for cid in ids}
        for future in as_completed(futures):
            cid = futures[future]
            try:
                success, term, error = future.result()
                if success:
                    with lock:
                        ok += 1
            except Exception as exc:
                LOGGER.exception("Stage 1 worker exception for %s: %s", cid, exc)
    
    LOGGER.info("Stage 1 finished: ok=%s total=%s (parallel, %d workers)", ok, len(ids), workers)


def _process_stage2_cluster(
    cid: str,
    priority_map: dict[str, int],
    sleep_seconds: float,
) -> tuple[bool, str | None, str | None]:
    """Process a single cluster for Stage 2 (item compilation). Returns (success, term, error)."""
    try:
        _mirror_cluster_into_compiled(cid)
        ingredient_core: dict[str, Any] = {}
        term = ""
        ingredient_exists = False
        skip_ai = False
        stubs: list[dict[str, Any]] = []
        with database_manager.get_session() as session:
            rec = session.get(database_manager.CompiledClusterRecord, cid)
            if rec is None or rec.term_status != "done":
                return (False, None, "Record not ready")
            if rec.priority is None:
                rec.priority = int(priority_map.get(cid, database_manager.DEFAULT_PRIORITY))
            term = (
                _clean(getattr(rec, "compiled_term", None))
                or _clean(getattr(rec, "raw_canonical_term", None))
                or _cluster_term_from_id(cid)
                or cid
            )
            ingredient_core, _, _ = _build_cluster_core(rec)
            ingredient_core["documentation"] = {"references": [], "last_verified": None}
            ingredient = _find_ingredient_by_terms(session, [term])
            if ingredient is not None:
                ingredient_exists = True
                _backfill_cluster_items_from_ingredient(session, cid, ingredient)

            item_rows = (
                session.query(database_manager.CompiledClusterItemRecord)
                .filter(database_manager.CompiledClusterItemRecord.cluster_id == cid)
                .filter(database_manager.CompiledClusterItemRecord.item_status != "done")
                .order_by(database_manager.CompiledClusterItemRecord.merged_item_form_id.asc())
                .limit(25)
                .all()
            )
            if not item_rows:
                skip_ai = True
            else:
                for it in item_rows:
                    raw = _safe_json_dict(getattr(it, "raw_item_json", None))
                    variation = _clean(raw.get("derived_variation") or getattr(it, "derived_variation", ""))
                    physical_form = _clean(raw.get("derived_physical_form") or getattr(it, "derived_physical_form", ""))
                    specs = raw.get("merged_specs") if isinstance(raw.get("merged_specs"), dict) else {}
                    form_bypass, variation_bypass = database_manager.derive_item_bypass_flags(
                        base_term=term,
                        variation=variation,
                        physical_form=physical_form,
                        form_bypass=(not bool(physical_form)),
                        variation_bypass=(not bool(variation)),
                    )
                    item_name = database_manager.derive_item_display_name(
                        base_term=term,
                        variation=variation,
                        variation_bypass=variation_bypass,
                        physical_form=physical_form,
                        form_bypass=form_bypass,
                    )
                    stubs.append(
                        {
                            "variation": variation,
                            "physical_form": physical_form,
                            "form_bypass": form_bypass,
                            "variation_bypass": variation_bypass,
                            "item_name": item_name,
                            "applications": ["Not Found"],
                            "specifications": specs,
                        }
                    )

                # Mark processing for these items
                now = datetime.now(timezone.utc)
                for it in item_rows:
                    it.item_status = "processing"
                    it.item_error = None
                    it.updated_at = now

        if skip_ai:
            if not ingredient_exists:
                _finalize_cluster_if_complete(cid)
            return (True, term, None)

        if not term:
            return (False, None, "No term")
        
        completed = ai_worker.complete_item_stubs(term, ingredient_core=ingredient_core, base_context={"term": term}, item_stubs=stubs)
        compiled_item_names = []
        with database_manager.get_session() as session:
            item_rows2 = (
                session.query(database_manager.CompiledClusterItemRecord)
                .filter(database_manager.CompiledClusterItemRecord.cluster_id == cid)
                .filter(database_manager.CompiledClusterItemRecord.item_status == "processing")
                .order_by(database_manager.CompiledClusterItemRecord.merged_item_form_id.asc())
                .limit(len(completed))
                .all()
            )
            now2 = datetime.now(timezone.utc)
            for idx, it in enumerate(item_rows2):
                payload = completed[idx] if idx < len(completed) else {}
                it.item_json = json.dumps(payload, ensure_ascii=False, sort_keys=True) if isinstance(payload, dict) else "{}"
                it.item_status = "done"
                it.item_compiled_at = now2
                it.item_error = None
                it.updated_at = now2
                item_name = payload.get("item_name") or payload.get("variation") or f"item-{idx+1}"
                compiled_item_names.append(item_name)
        
        for item_name in compiled_item_names:
            LOGGER.info("Stage 2 item: %s -> %s", term, item_name)

        if not ingredient_exists:
            _finalize_cluster_if_complete(cid)
        return (True, term, None)
    except Exception as exc:
        with database_manager.get_session() as session:
            rows = (
                session.query(database_manager.CompiledClusterItemRecord)
                .filter(database_manager.CompiledClusterItemRecord.cluster_id == cid)
                .filter(database_manager.CompiledClusterItemRecord.item_status == "processing")
                .all()
            )
            now = datetime.now(timezone.utc)
            for r in rows:
                r.item_status = "error"
                r.item_error = str(exc)
                r.updated_at = now
        LOGGER.exception("Stage 2 failed for cluster %s: %s", cid, exc)
        return (False, None, str(exc))
    finally:
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))


def run_stage2_item_compilation(*, cluster_id: str | None, limit: int | None, sleep_seconds: float, workers: int = 1) -> None:
    """Stage 2: compile/enrich items for clusters whose term is already normalized."""
    ids = _select_stage2_cluster_ids(limit=limit, cluster_id=cluster_id)
    if not ids:
        LOGGER.info("Stage 2: no clusters pending item compilation.")
        return
    priority_map = database_manager.build_cluster_priority_map()
    
    workers = max(1, min(workers, 10))  # Cap at 10 workers
    LOGGER.info("Stage 2: processing %d clusters with %d worker(s)", len(ids), workers)
    
    if workers == 1:
        # Sequential processing (original behavior)
        ok = 0
        for cid in ids:
            success, term, error = _process_stage2_cluster(cid, priority_map, sleep_seconds)
            if success:
                ok += 1
        LOGGER.info("Stage 2 finished: ok=%s clusters=%s", ok, len(ids))
        return
    
    # Parallel processing with multiple workers
    ok = 0
    lock = threading.Lock()
    
    def worker_task(cid: str) -> tuple[bool, str | None, str | None]:
        return _process_stage2_cluster(cid, priority_map, sleep_seconds)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(worker_task, cid): cid for cid in ids}
        for future in as_completed(futures):
            cid = futures[future]
            try:
                success, term, error = future.result()
                if success:
                    with lock:
                        ok += 1
            except Exception as exc:
                LOGGER.exception("Stage 2 worker exception for %s: %s", cid, exc)
    
    LOGGER.info("Stage 2 finished: ok=%s clusters=%s (parallel, %d workers)", ok, len(ids), workers)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile clustered terms (stage 1) and items (stage 2) via OpenAI")
    parser.add_argument(
        "--stage",
        choices=["1", "2"],
        default=os.getenv("COMPILER_STAGE", "1"),
        help="1=term completion/normalization, 2=item compilation/enrichment.",
    )
    parser.add_argument(
        "--cluster-id",
        default=os.getenv("COMPILER_CLUSTER_ID", ""),
        help="Exact cluster_id to process (optional).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("COMPILER_LIMIT", str(DEFAULT_CLUSTER_LIMIT))),
        help="Max clusters to process in this run.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS, help="Delay between API calls (per worker)")
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=DEFAULT_WORKERS,
        help="Number of parallel workers (1-10). For gpt-4o-mini with 2M TPM limit, use 3-5 workers. Default: 1",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(
        level=os.getenv("COMPILER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    args = parse_args(argv or sys.argv[1:])
    stage = str(getattr(args, "stage", "1") or "1").strip()
    cid = str(getattr(args, "cluster_id", "") or "").strip() or None
    limit = int(getattr(args, "limit", 0) or 0)
    limit = limit if limit > 0 else None
    workers = int(getattr(args, "workers", 1) or 1)
    if stage == "1":
        run_stage1_term_completion(cluster_id=cid, limit=limit, sleep_seconds=float(args.sleep_seconds or 0), workers=workers)
        return
    run_stage2_item_compilation(cluster_id=cid, limit=limit, sleep_seconds=float(args.sleep_seconds or 0), workers=workers)


if __name__ == "__main__":
    main()
