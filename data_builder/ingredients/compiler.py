"""Iterative orchestrator that builds the ingredient library one record at a time."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, MutableMapping, Set

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
DEFAULT_TERMS_FILE = BASE_DIR / "terms.json"
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


def _fetch_existing_compiled_payload(term: str) -> dict[str, Any] | None:
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        row = session.get(database_manager.IngredientRecord, term)
        if row is None:
            return None
        blob = getattr(row, "payload_json", None)
        payload = _safe_json_dict(blob if isinstance(blob, str) else "{}")
        return payload or None


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
        if limit:
            q = q.limit(int(limit))
        return [str(r[0]) for r in q.all() if r and r[0]]


def _select_stage2_cluster_ids(*, limit: int | None, cluster_id: str | None) -> list[str]:
    """Select clusters whose term is compiled but have pending items (Stage 2 pending)."""
    database_manager.ensure_tables_exist()
    cid = (cluster_id or "").strip() or None
    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.CompiledClusterRecord.cluster_id)
            .join(
                database_manager.CompiledClusterItemRecord,
                database_manager.CompiledClusterItemRecord.cluster_id == database_manager.CompiledClusterRecord.cluster_id,
            )
            .filter(database_manager.CompiledClusterRecord.term_status == "done")
            .filter(database_manager.CompiledClusterItemRecord.item_status != "done")
        )
        if cid:
            q = q.filter(database_manager.CompiledClusterRecord.cluster_id == cid)
        q = q.distinct().order_by(database_manager.CompiledClusterRecord.cluster_id.asc())
        if limit:
            q = q.limit(int(limit))
        return [str(r[0]) for r in q.all() if r and r[0]]


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
                "merged_specs": _safe_json_dict(getattr(mif, "merged_specs_json", None)),
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
                    "merged_specs": _safe_json_dict(getattr(mif, "merged_specs_json", None)),
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


def run_stage1_term_completion(*, cluster_id: str | None, limit: int | None, sleep_seconds: float) -> None:
    """Stage 1: complete + normalize the term for each raw cluster."""
    ids = _select_stage1_cluster_ids(limit=limit, cluster_id=cluster_id)
    if not ids:
        LOGGER.info("Stage 1: no clusters pending term completion.")
        return
    ok = 0
    for cid in ids:
        try:
            _mirror_cluster_into_compiled(cid)
            context = _build_cluster_context(cid)
            with database_manager.get_session() as session:
                rec = session.get(database_manager.CompiledClusterRecord, cid)
                if rec is None:
                    continue
                rec.term_status = "processing"
                rec.term_error = None
                rec.updated_at = datetime.now(timezone.utc)
            result = ai_worker.normalize_cluster_term(cid, context)
            term = _clean(result.get("term"))
            core = result.get("ingredient_core") if isinstance(result.get("ingredient_core"), dict) else {}
            dq = result.get("data_quality") if isinstance(result.get("data_quality"), dict) else {}

            def extract_field(field_data):
                """Extract value from field status wrapper or plain value."""
                if isinstance(field_data, dict) and "value" in field_data:
                    status = field_data.get("status", "")
                    if status in ("found", ""):
                        return _clean(field_data.get("value"))
                    return None  # not_found or not_applicable
                return _clean(field_data)  # plain value fallback

            with database_manager.get_session() as session:
                rec = session.get(database_manager.CompiledClusterRecord, cid)
                if rec is None:
                    continue
                rec.compiled_term = term or rec.raw_canonical_term or cid
                rec.origin = extract_field(core.get("origin")) or rec.raw_origin
                rec.ingredient_category = extract_field(core.get("ingredient_category")) or rec.raw_ingredient_category
                rec.refinement_level = extract_field(core.get("base_refinement")) or extract_field(core.get("refinement_level")) or None
                rec.derived_from = extract_field(core.get("derived_from")) or None
                rec.botanical_name = extract_field(core.get("botanical_name")) or None
                rec.inci_name = extract_field(core.get("inci_name")) or None
                rec.cas_number = extract_field(core.get("cas_number")) or None
                rec.seed_category = None
                rec.payload_json = json.dumps(
                    {"stage1": {"term": rec.compiled_term, "ingredient_core": core, "data_quality": dq}},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                rec.term_status = "done"
                rec.term_compiled_at = datetime.now(timezone.utc)
                rec.term_error = None
                rec.updated_at = datetime.now(timezone.utc)
            ok += 1
        except Exception as exc:  # pylint: disable=broad-except
            with database_manager.get_session() as session:
                rec = session.get(database_manager.CompiledClusterRecord, cid)
                if rec is not None:
                    rec.term_status = "error"
                    rec.term_error = str(exc)
                    rec.updated_at = datetime.now(timezone.utc)
            LOGGER.exception("Stage 1 failed for cluster %s: %s", cid, exc)
        time.sleep(float(sleep_seconds or 0))
    LOGGER.info("Stage 1 finished: ok=%s total=%s", ok, len(ids))


def run_stage2_item_compilation(*, cluster_id: str | None, limit: int | None, sleep_seconds: float) -> None:
    """Stage 2: compile/enrich items for clusters whose term is already normalized."""
    ids = _select_stage2_cluster_ids(limit=limit, cluster_id=cluster_id)
    if not ids:
        LOGGER.info("Stage 2: no clusters pending item compilation.")
        return
    ok = 0
    for cid in ids:
        try:
            _mirror_cluster_into_compiled(cid)
            with database_manager.get_session() as session:
                rec = session.get(database_manager.CompiledClusterRecord, cid)
                if rec is None or rec.term_status != "done":
                    continue
                term = _clean(getattr(rec, "compiled_term", None)) or _clean(getattr(rec, "raw_canonical_term", None)) or cid
                ingredient_core = {
                    "origin": getattr(rec, "origin", None),
                    "ingredient_category": getattr(rec, "ingredient_category", None),
                    "refinement_level": getattr(rec, "refinement_level", None),
                    "derived_from": getattr(rec, "derived_from", None),
                    "category": getattr(rec, "ingredient_category", None),
                    "botanical_name": getattr(rec, "botanical_name", None),
                    "inci_name": getattr(rec, "inci_name", None),
                    "cas_number": getattr(rec, "cas_number", None),
                    "short_description": None,
                    "detailed_description": None,
                    "documentation": {"references": [], "last_verified": None},
                }
                item_rows = (
                    session.query(database_manager.CompiledClusterItemRecord)
                    .filter(database_manager.CompiledClusterItemRecord.cluster_id == cid)
                    .filter(database_manager.CompiledClusterItemRecord.item_status != "done")
                    .order_by(database_manager.CompiledClusterItemRecord.merged_item_form_id.asc())
                    .limit(25)
                    .all()
                )
                stubs: list[dict[str, Any]] = []
                for it in item_rows:
                    raw = _safe_json_dict(getattr(it, "raw_item_json", None))
                    variation = _clean(raw.get("derived_variation") or getattr(it, "derived_variation", ""))
                    physical_form = _clean(raw.get("derived_physical_form") or getattr(it, "derived_physical_form", ""))
                    specs = raw.get("merged_specs") if isinstance(raw.get("merged_specs"), dict) else {}
                    stubs.append(
                        {
                            "variation": variation,
                            "physical_form": physical_form,
                            "form_bypass": (not bool(physical_form)),
                            "variation_bypass": (not bool(variation)),
                            "applications": ["Unknown"],
                            "specifications": specs,
                        }
                    )

                # Mark processing for these items
                now = datetime.now(timezone.utc)
                for it in item_rows:
                    it.item_status = "processing"
                    it.item_error = None
                    it.updated_at = now

            completed = ai_worker.complete_item_stubs(term, ingredient_core=ingredient_core, base_context={"term": term}, item_stubs=stubs)
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
            ok += 1
        except Exception as exc:  # pylint: disable=broad-except
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
        time.sleep(float(sleep_seconds or 0))
    LOGGER.info("Stage 2 finished: ok=%s clusters=%s", ok, len(ids))


def process_next_term(*, sleep_seconds: float, min_priority: int, phase: str, seed_category: str | None) -> bool:
    """Process a single pending task honoring the priority floor. Returns False when queue is empty."""

    task = database_manager.get_next_pending_task(min_priority=min_priority, seed_category=seed_category)
    if not task:
        LOGGER.info("No pending tasks found at priority >= %s; compiler is finished.", min_priority)
        return False

    term, priority, seed_category = task
    LOGGER.info("Processing term: %s (priority %s)", term, priority)
    database_manager.update_task_status(term, "processing")

    try:
        normalized = database_manager.get_normalized_term(term) or {}
        phase_clean = (phase or "full").strip().lower()

        # Deterministic seed items from ingestion: compiler should complete these, not invent them.
        with database_manager.get_session() as session:
            seed_rows = (
                session.query(database_manager.MergedItemForm)
                .filter(database_manager.MergedItemForm.derived_term == term)
                .order_by(database_manager.MergedItemForm.id.asc())
                .all()
            )
        seed_items: list[dict[str, Any]] = []
        for r in seed_rows:
            try:
                specs = json.loads(r.merged_specs_json or "{}")
                if not isinstance(specs, dict):
                    specs = {}
            except Exception:
                specs = {}
            variation = (r.derived_variation or "").strip()
            physical_form = (r.derived_physical_form or "").strip()
            seed_items.append(
                {
                    "variation": variation,
                    "physical_form": physical_form,
                    # Inventory: if the ingestor didn't provide a form, treat as identity/bypass to avoid quarantine.
                    "form_bypass": (not bool(physical_form)),
                    "variation_bypass": (not bool(variation)),
                    "applications": ["Unknown"],
                    "specifications": specs,
                }
            )
        if seed_items:
            normalized["seed_items"] = seed_items

        if phase_clean == "core":
            core_payload = ai_worker.compile_core(term, base_context=normalized)
            ingredient_core = core_payload.get("ingredient_core") if isinstance(core_payload.get("ingredient_core"), dict) else {}
            confidence = core_payload.get("data_quality", {}).get("confidence") if isinstance(core_payload.get("data_quality"), dict) else 0.7
            caveats = core_payload.get("data_quality", {}).get("caveats") if isinstance(core_payload.get("data_quality"), dict) else []
            payload = {
                "ingredient": {
                    **ingredient_core,
                    "common_name": term,
                    # Allow DB writer to seed a deterministic base item.
                    "items": [],
                    # Keep stable fields even if AI omitted them.
                    "documentation": ingredient_core.get("documentation") or {"references": [], "last_verified": None},
                },
                "data_quality": {"confidence": float(confidence) if isinstance(confidence, (int, float)) else 0.7, "caveats": caveats if isinstance(caveats, list) else []},
            }
        else:
            existing_payload = _fetch_existing_compiled_payload(term) if phase_clean == "items" else None
            existing_ingredient = existing_payload.get("ingredient") if isinstance((existing_payload or {}).get("ingredient"), dict) else {}

            # Term completion (core) happens first unless we're strictly in "items" mode with an existing core.
            if phase_clean == "items" and existing_ingredient:
                ingredient_core = dict(existing_ingredient)
                core_conf = (existing_payload.get("data_quality", {}) or {}).get("confidence") if isinstance(existing_payload.get("data_quality"), dict) else None
                core_caveats = (existing_payload.get("data_quality", {}) or {}).get("caveats") if isinstance(existing_payload.get("data_quality"), dict) else []
            else:
                core_payload = ai_worker.compile_core(term, base_context=normalized)
                ingredient_core = core_payload.get("ingredient_core") if isinstance(core_payload.get("ingredient_core"), dict) else {}
                core_conf = core_payload.get("data_quality", {}).get("confidence") if isinstance(core_payload.get("data_quality"), dict) else None
                core_caveats = core_payload.get("data_quality", {}).get("caveats") if isinstance(core_payload.get("data_quality"), dict) else []

            items_payload = ai_worker.compile_items(term, ingredient_core=ingredient_core, base_context=normalized)
            items = items_payload.get("items") if isinstance(items_payload.get("items"), list) else []
            taxonomy_payload = ai_worker.compile_taxonomy(term, ingredient_core=ingredient_core, items=[it for it in items if isinstance(it, dict)])
            taxonomy = taxonomy_payload.get("taxonomy") if isinstance(taxonomy_payload.get("taxonomy"), dict) else {}

            # Assemble final payload matching the DB writer expectations.
            ingredient: Dict[str, Any] = dict(ingredient_core)
            ingredient["common_name"] = term
            ingredient["items"] = items
            ingredient["taxonomy"] = taxonomy
            if "documentation" not in ingredient:
                ingredient["documentation"] = {"references": [], "last_verified": None}

            caveats: list[str] = []
            for blob in (core_caveats, items_payload.get("data_quality", {}).get("caveats") if isinstance(items_payload.get("data_quality"), dict) else []):
                if isinstance(blob, list):
                    for c in blob:
                        if isinstance(c, str) and c.strip():
                            caveats.append(c.strip())

            confidence = core_conf if isinstance(core_conf, (int, float)) else 0.7
            payload = {"ingredient": ingredient, "data_quality": {"confidence": float(confidence), "caveats": sorted(set(caveats))}}

        # Persist compiled payload into the DB (source of truth).
        database_manager.upsert_compiled_ingredient(term, payload, seed_category=seed_category)

        # Optional legacy artifact: write one JSON file per ingredient (disabled by default).
        if WRITE_INGREDIENT_FILES:
            slug = slugify(term)
            save_payload(payload, slug)
        update_lookup_files(payload)
        database_manager.update_task_status(term, "completed")
        LOGGER.info("Successfully compiled %s", term)
    except Exception as exc:  # pylint: disable=broad-except
        database_manager.update_task_status(term, "error")
        LOGGER.exception("Failed to process %s: %s", term, exc)

    time.sleep(sleep_seconds)
    return True


def run_compiler(*, sleep_seconds: float, max_ingredients: int | None, min_priority: int, phase: str, seed_category: str | None) -> None:
    ensure_output_dirs()
    iterations = 0
    while True:
        if max_ingredients and iterations >= max_ingredients:
            LOGGER.info("Reached ingredient cap (%s); stopping.", max_ingredients)
            break
        if not process_next_term(sleep_seconds=sleep_seconds, min_priority=min_priority, phase=phase, seed_category=seed_category):
            break
        iterations += 1


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile cluster terms (stage 1) and items (stage 2) via OpenAI")
    parser.add_argument(
        "--mode",
        choices=["cluster", "legacy"],
        default=os.getenv("COMPILER_MODE", "cluster"),
        help="cluster=cluster-based stage runner (recommended); legacy=term-queue compiler (old).",
    )
    parser.add_argument(
        "--stage",
        choices=["1", "2"],
        default=os.getenv("COMPILER_STAGE", "1"),
        help="cluster mode only: 1=term completion/normalization, 2=item compilation/enrichment.",
    )
    parser.add_argument(
        "--cluster-id",
        default=os.getenv("COMPILER_CLUSTER_ID", ""),
        help="cluster mode only: exact cluster_id to process (optional).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=int(os.getenv("COMPILER_LIMIT", str(DEFAULT_CLUSTER_LIMIT))),
        help="cluster mode only: max clusters to process in this run.",
    )
    parser.add_argument("--terms-file", default=str(DEFAULT_TERMS_FILE), help="Seed term file (JSON array of {term, priority})")
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS, help="Delay between API calls")
    parser.add_argument("--max-ingredients", type=int, default=0, help="Optional cap for number of processed ingredients in this run")
    parser.add_argument("--min-priority", type=int, default=database_manager.MIN_PRIORITY, help="Minimum priority (1-10) required to process a queued ingredient")
    parser.add_argument(
        "--phase",
        choices=["core", "items", "full"],
        default=os.getenv("COMPILER_PHASE", "full"),
        help="Compiler phase: core=complete term core only; items=compile/complete items for existing cores; full=core+items+taxonomy (default).",
    )
    parser.add_argument(
        "--seed-category",
        default=os.getenv("COMPILER_SEED_CATEGORY", ""),
        help="Optional exact-match filter to only process queued tasks for this primary seed_category.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(
        level=os.getenv("COMPILER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    args = parse_args(argv or sys.argv[1:])

    mode = str(getattr(args, "mode", "cluster") or "cluster").strip().lower()
    if mode == "cluster":
        stage = str(getattr(args, "stage", "1") or "1").strip()
        cid = str(getattr(args, "cluster_id", "") or "").strip() or None
        limit = int(getattr(args, "limit", 0) or 0)
        limit = limit if limit > 0 else None
        if stage == "1":
            run_stage1_term_completion(cluster_id=cid, limit=limit, sleep_seconds=float(args.sleep_seconds or 0))
            return
        run_stage2_item_compilation(cluster_id=cid, limit=limit, sleep_seconds=float(args.sleep_seconds or 0))
        return

    # Optional legacy queue seeding from a terms.json file.
    # Preferred flow: term_collector seeds compiler_state.db directly.
    try:
        if args.terms_file and Path(args.terms_file).exists():
            database_manager.initialize_queue(args.terms_file)
    except FileNotFoundError:
        LOGGER.warning("Terms file %s not found; queue will only use existing entries.", args.terms_file)

    run_compiler(
        sleep_seconds=args.sleep_seconds,
        max_ingredients=args.max_ingredients or None,
        min_priority=max(database_manager.MIN_PRIORITY, min(args.min_priority, database_manager.MAX_PRIORITY)),
        phase=str(args.phase or "full").strip().lower(),
        seed_category=(str(args.seed_category).strip() or None),
    )


if __name__ == "__main__":
    main()
