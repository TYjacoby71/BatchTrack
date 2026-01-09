"""Iterative orchestrator that builds the ingredient library one record at a time."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
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


def _build_items_override_from_ingestion(term: str) -> list[dict]:
    """Build item stubs from deterministic ingestion (merged_item_forms)."""
    database_manager.ensure_tables_exist()
    out: list[dict] = []

    def _as_dict(text: Any) -> dict:
        try:
            if isinstance(text, dict):
                return text
            if not isinstance(text, str) or not text.strip():
                return {}
            v = json.loads(text)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}

    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.MergedItemForm)
            .filter(database_manager.MergedItemForm.derived_term == term)
            .order_by(database_manager.MergedItemForm.id.asc())
        )
        for mif in q.all():
            variation = (getattr(mif, "derived_variation", "") or "").strip()
            physical_form = (getattr(mif, "derived_physical_form", "") or "").strip()
            variation_bypass = not bool(variation)
            form_bypass = not bool(physical_form)
            specs = _as_dict(getattr(mif, "merged_specs_json", "{}"))
            out.append(
                {
                    "variation": variation,
                    "physical_form": physical_form,
                    "variation_bypass": bool(variation_bypass),
                    "form_bypass": bool(form_bypass),
                    "synonyms": [],
                    "applications": [],
                    "function_tags": [],
                    "safety_tags": [],
                    "sds_hazards": [],
                    "storage": {},
                    "specifications": specs,
                    "sourcing": {},
                }
            )
    return out


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


def process_next_term(sleep_seconds: float, min_priority: int) -> bool:
    """Process a single pending task honoring the priority floor. Returns False when queue is empty."""

    task = database_manager.get_next_pending_task(min_priority=min_priority)
    if not task:
        LOGGER.info("No pending tasks found at priority >= %s; compiler is finished.", min_priority)
        return False

    term, priority, seed_category = task
    LOGGER.info("Processing term: %s (priority %s)", term, priority)
    database_manager.update_task_status(term, "processing")

    try:
        normalized = database_manager.get_normalized_term(term) or {}
        items_override = _build_items_override_from_ingestion(term)
        payload = ai_worker.get_ingredient_data(
            term,
            base_context=normalized,
            items_override=items_override if items_override else None,
        )
        if not isinstance(payload, dict) or payload.get("error"):
            raise RuntimeError(payload.get("error") if isinstance(payload, dict) else "Unknown AI failure")

        ingredient = validate_payload(payload)
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


def run_compiler(sleep_seconds: float, max_ingredients: int | None, min_priority: int) -> None:
    ensure_output_dirs()
    iterations = 0
    while True:
        if max_ingredients and iterations >= max_ingredients:
            LOGGER.info("Reached ingredient cap (%s); stopping.", max_ingredients)
            break
        if not process_next_term(sleep_seconds, min_priority):
            break
        iterations += 1


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Iteratively compile ingredient data via OpenAI")
    parser.add_argument("--terms-file", default=str(DEFAULT_TERMS_FILE), help="Seed term file (JSON array of {term, priority})")
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS, help="Delay between API calls")
    parser.add_argument("--max-ingredients", type=int, default=0, help="Optional cap for number of processed ingredients in this run")
    parser.add_argument("--min-priority", type=int, default=database_manager.MIN_PRIORITY, help="Minimum priority (1-10) required to process a queued ingredient")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    logging.basicConfig(
        level=os.getenv("COMPILER_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    args = parse_args(argv or sys.argv[1:])

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
    )


if __name__ == "__main__":
    main()
