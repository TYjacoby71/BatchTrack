"""Derive deterministic function tags + master categories for SourceItem rows.

Inputs:
- SourceItem: derived_variation, derived_physical_form, ingredient_category, origin, payload_json
- SourceCatalog: (not required here)
- taxonomy_constants.MASTER_CATEGORY_RULE_SEED

Outputs (written into source_items):
- derived_function_tags_json (list[str])
- derived_master_categories_json (list[str])

Policy:
- Prefer CosIng 'Function' column (authoritative) for function tags.
- Use a small set of high-confidence name/variation-based inferences (e.g., Gum -> Thickener).
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

from . import database_manager
from .taxonomy_constants import MASTER_CATEGORY_RULE_SEED

LOGGER = logging.getLogger(__name__)


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _parse_cosing_functions(payload: dict[str, Any]) -> list[str]:
    raw = _clean(payload.get("Function"))
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def _map_cosing_function_to_tags(func: str) -> list[str]:
    """
    Map CosIng function strings to normalized function tags.
    CosIng functions often look like:
    - "SURFACTANT - CLEANSING"
    - "SKIN CONDITIONING - EMOLLIENT"
    """
    f = _clean(func).upper()
    if not f or f == "NOT REPORTED":
        return []

    tags: set[str] = set()

    # Broad categories
    if "SURFACTANT" in f or "CLEANSING" in f:
        tags.add("Surfactant")
    if "EMULSIFYING" in f:
        tags.add("Emulsifier")
    if "EMULSION STABILISING" in f or "FILM FORMING" in f or "BINDING" in f or "CHELATING" in f or "ANTIFOAMING" in f:
        tags.add("Stabilizer")
    if "VISCOSITY CONTROLLING" in f:
        tags.add("Thickener")

    if "PRESERVATIVE" in f or "ANTIMICROBIAL" in f:
        tags.add("Preservative")
    if "ANTIOXIDANT" in f or "LIGHT STABILIZER" in f:
        tags.add("Antioxidant")
    if "BUFFERING" in f or "PH ADJUSTERS" in f:
        tags.add("Acid")

    if "COLORANT" in f or "HAIR DYEING" in f or "BLEACHING" in f:
        tags.add("Colorant")
    if "UV FILTER" in f or "UV ABSORBER" in f:
        tags.add("UV Filter")

    if "PERFUMING" in f or "FRAGRANCE" in f or "MASKING" in f or "DEODORANT" in f or "REFRESHING" in f:
        tags.add("Fragrance")

    if "SKIN CONDITIONING" in f or "SKIN PROTECTING" in f or "EMOLLIENT" in f or "HUMECTANT" in f or "SOOTHING" in f or "MOISTURISING" in f or "TONIC" in f:
        tags.add("Skin Conditioning")

    if "HAIR CONDITIONING" in f:
        tags.add("Hair Conditioning")

    if "SOLVENT" in f:
        tags.add("Solvent")

    if "ANTI-ACNE" in f or "ANTI-SEBUM" in f or "ANTI-SEBORRHEIC" in f:
        tags.add("Active")

    return sorted(tags)


def _derive_function_tags(item: database_manager.SourceItem) -> list[str]:
    tags: set[str] = set()
    payload: dict[str, Any] = {}
    try:
        payload = json.loads(item.payload_json or "{}")
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    # CosIng authoritative function tags
    if (item.source or "").strip().lower() == "cosing":
        for f in _parse_cosing_functions(payload):
            for mapped in _map_cosing_function_to_tags(f):
                tags.add(mapped)

    # High-confidence derivations from variation/form (kept conservative)
    v = _clean(item.derived_variation)
    form = _clean(item.derived_physical_form)
    if v in {"Gum", "Gel"} or form in {"Gum", "Gel"}:
        tags.add("Thickener")
        tags.add("Stabilizer")
    if v in {"Sulfate", "Sulfonate", "Sulfosuccinate", "Glucoside", "Betaine", "Amine Oxide", "Sarcosinate", "Taurate", "Sultaine", "Amphoacetate"}:
        tags.add("Surfactant")
    if v in {"Essential Oil", "Absolute", "Concrete"}:
        tags.add("Fragrance")

    # If CosIng already provides functions, do not add redundant low-signal heuristics.
    # (we already did only high-confidence inferences above)
    return sorted(tags)


def _build_master_rule_index() -> dict[tuple[str, str], set[str]]:
    idx: dict[tuple[str, str], set[str]] = {}
    for master, source_type, source_value in MASTER_CATEGORY_RULE_SEED:
        key = (source_type.strip(), source_value.strip())
        idx.setdefault(key, set()).add(master.strip())
    return idx


def _derive_master_categories(
    *,
    ingredient_category: str,
    variation: str,
    physical_form: str,
    function_tags: list[str],
) -> list[str]:
    rules = _build_master_rule_index()
    out: set[str] = set()
    if ingredient_category:
        out |= rules.get(("ingredient_category", ingredient_category), set())
    if variation:
        out |= rules.get(("variation", variation), set())
    if physical_form:
        out |= rules.get(("physical_form", physical_form), set())
    for tag in function_tags:
        out |= rules.get(("function_tag", tag), set())
    return sorted(out)


def derive_tags(*, limit: int = 0) -> dict[str, int]:
    database_manager.ensure_tables_exist()
    updated = 0
    scanned = 0
    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceItem)
        if limit and int(limit) > 0:
            q = q.limit(int(limit))
        for item in q.yield_per(1000):
            scanned += 1
            func_tags = _derive_function_tags(item)
            masters = _derive_master_categories(
                ingredient_category=_clean(item.ingredient_category),
                variation=_clean(item.derived_variation),
                physical_form=_clean(item.derived_physical_form),
                function_tags=func_tags,
            )
            func_json = json.dumps(func_tags, ensure_ascii=False)
            master_json = json.dumps(masters, ensure_ascii=False)
            if (item.derived_function_tags_json or "[]") != func_json or (item.derived_master_categories_json or "[]") != master_json:
                item.derived_function_tags_json = func_json
                item.derived_master_categories_json = master_json
                updated += 1
    return {"scanned": scanned, "updated": updated}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Derive function tags and master categories for source_items")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    stats = derive_tags(limit=int(args.limit or 0))
    LOGGER.info("derived source item tags: %s", stats)


if __name__ == "__main__":
    main()

