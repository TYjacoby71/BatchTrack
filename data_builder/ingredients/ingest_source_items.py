"""Item-first ingestion for CosIng (INCI) + TGSC.

This script reads the bundled CSV sources and writes into compiler_state.db:
- source_items: every source row as an *item* (with derived definition linkage)
- normalized_terms: deduped derived definition terms for later queueing/compilation

Why:
- The previous normalizer treated item-like names as base terms (e.g., "Beetroot Powder"),
  which pollutes the lineage tree and the compiler queue.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import database_manager
from .item_parser import (
    derive_definition_term,
    extract_plant_part,
    extract_variation_and_physical_form,
    infer_origin,
    infer_primary_category,
    infer_refinement,
)

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_SOURCES_DIR = BASE_DIR / "data_sources"


def _sha_key(*parts: str) -> str:
    joined = "|".join([p.strip() for p in parts if p is not None])
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()  # deterministic


def _first_cas(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    import re
    m = re.search(r"\b(\d{2,7}-\d{2}-\d)\b", v)
    return m.group(1) if m else ""


def _cas_list(value: str) -> list[str]:
    """Extract all CAS tokens from a field (supports '/' separated lists)."""
    import re
    v = (value or "").strip()
    if not v:
        return []
    tokens = re.findall(r"\b(\d{2,7}-\d{2}-\d)\b", v)
    # de-dupe while preserving order
    seen = set()
    out: list[str] = []
    for t in tokens:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _iter_cosing_rows(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=1):
            # Preserve 1:1 row traceability
            cosing_ref = (row.get("COSING Ref No") or "").strip()
            row["__rownum__"] = idx
            row["__cosing_ref__"] = cosing_ref
            row["__source_row_id__"] = cosing_ref or f"row:{idx}"
            yield row


def _iter_tgsc_rows(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for idx, row in enumerate(reader, start=1):
            url = (row.get("url") or "").strip()
            row["__rownum__"] = idx
            row["__tgsc_url__"] = url
            row["__source_row_id__"] = url or f"row:{idx}"
            yield row


def _pick_rows(
    *,
    cosing_rows: list[dict[str, Any]],
    tgsc_rows: list[dict[str, Any]],
    sample_size: Optional[int],
    seed: Optional[int],
    include: list[str],
) -> list[tuple[str, dict[str, Any]]]:
    """Return a list of (source, row) to ingest."""
    include_norm_raw = [i.strip().lower() for i in include if (i or "").strip()]
    # Minimal alias expansion for common maker names -> common INCI/binomial tokens.
    alias_map = {
        "lavender": ["lavandula"],
        "jojoba": ["simmondsia"],
    }
    include_norm: list[str] = []
    for token in include_norm_raw:
        include_norm.append(token)
        for k, aliases in alias_map.items():
            if k in token:
                include_norm.extend(aliases)

    def _row_name(source: str, row: dict[str, Any]) -> str:
        if source == "cosing":
            return (row.get("INCI name") or row.get("INCI Name") or "").strip()
        return (row.get("common_name") or row.get("name") or "").strip()

    def _matches_includes(source: str, row: dict[str, Any]) -> bool:
        if not include_norm:
            return False
        name = _row_name(source, row).lower()
        return any(token in name for token in include_norm)

    # Build full pool
    pool: list[tuple[str, dict[str, Any]]] = [("cosing", r) for r in cosing_rows] + [("tgsc", r) for r in tgsc_rows]

    # Pull includes first (one best match per include token)
    selected: list[tuple[str, dict[str, Any]]] = []
    seen_keys: set[str] = set()
    for token in include_norm:
        best: tuple[int, str, dict[str, Any]] | None = None
        for source, row in pool:
            name = _row_name(source, row)
            if not name:
                continue
            name_l = name.lower()
            if token not in name_l:
                continue
            key = f"{source}|{name}".lower()
            if key in seen_keys:
                continue
            # Prefer oils for these includes when multiple matches exist.
            score = 0
            if " oil" in name_l or name_l.endswith("oil"):
                score += 10
            if " seed oil" in name_l:
                score += 2
            # Prefer CosIng exact INCI strings slightly (often cleaner)
            if source == "cosing":
                score += 1
            best_score = best[0] if best else -9999
            if score > best_score:
                best = (score, source, row)
        if best:
            _, source, row = best
            name = _row_name(source, row)
            key = f"{source}|{name}".lower()
            selected.append((source, row))
            seen_keys.add(key)

    if sample_size is None:
        # If no sampling requested, ingest everything.
        return selected + [(s, r) for s, r in pool if f"{s}|{_row_name(s, r)}".lower() not in seen_keys and _row_name(s, r)]

    # Fill remaining with random sample from the rest
    remaining = [(s, r) for s, r in pool if _row_name(s, r) and f"{s}|{_row_name(s, r)}".lower() not in seen_keys]
    rng = random.Random(seed)  # deterministic if seed provided
    rng.shuffle(remaining)
    needed = max(0, int(sample_size) - len(selected))
    selected.extend(remaining[:needed])
    return selected


def ingest_sources(
    *,
    cosing_path: Path,
    tgsc_path: Path,
    limit: Optional[int] = None,
    sample_size: Optional[int] = None,
    seed: Optional[int] = None,
    include: Optional[list[str]] = None,
    write_terms: bool = True,
) -> tuple[int, int]:
    """Ingest source items and derived normalized terms.

    Returns:
        (inserted_source_items, inserted_normalized_terms)
    """
    database_manager.ensure_tables_exist()

    source_rows: List[dict[str, Any]] = []
    normalized_terms: dict[str, dict[str, Any]] = {}

    def _register_item(*, source: str, raw_name: str, inci_name: str = "", cas_number: str = "", payload: dict) -> None:
        raw = (raw_name or "").strip()
        if not raw:
            return
        definition = derive_definition_term(raw)
        origin = infer_origin(raw)
        ingredient_category = infer_primary_category(definition, origin, raw_name=raw) if definition else ""
        refinement_level = infer_refinement(definition or raw, raw)
        variation, physical_form = extract_variation_and_physical_form(raw)
        derived_part = extract_plant_part(raw)
        # CosIng provides descriptions that explicitly distinguish volatile (essential) oils.
        # If the INCI contains "... OIL" but is not a seed/nut/kernel oil, and the description
        # says "volatile oil" (or clearly indicates an essential oil), treat as Essential Oil deterministically.
        if source == "cosing" and " oil" in raw.lower():
            lower = raw.lower()
            if not any(tok in lower for tok in ("seed oil", "kernel oil", "nut oil")):
                desc = (payload.get("Chem/IUPAC Name / Description") or "").strip().lower()
                funcs = (payload.get("Function") or "").strip().lower()
                # Guardrail: only essential-oil classify when CosIng also marks it as perfuming/fragrance.
                is_perfuming = any(k in funcs for k in ("fragrance", "perfuming", "masking"))
                is_essential_oil_desc = (
                    ("volatile oil" in desc)
                    or ("essential oil" in desc)
                    or ("oil distilled" in desc)
                    or ("distilled" in desc and "oil" in desc)
                )
                if is_essential_oil_desc and is_perfuming:
                    variation, physical_form = "Essential Oil", "Oil"

        status = "linked" if definition else "orphan"
        reason = None
        if not definition:
            reason = "Unable to derive definition term from source item"

        # 1:1 traceability key: tie to the *source row id* (not content), so we never collapse
        # distinct source rows into one item.
        source_row_id = str(payload.get("__source_row_id__") or "").strip()
        source_row_number = payload.get("__rownum__")
        source_ref = (
            (payload.get("__cosing_ref__") or "").strip()
            if source == "cosing"
            else (payload.get("__tgsc_url__") or "").strip()
        )
        key = _sha_key(source, source_row_id or f"row:{source_row_number or ''}", raw)
        cas_numbers = _cas_list(cas_number or "")
        primary_cas = cas_numbers[0] if cas_numbers else ""
        content_hash = _sha_key(source, raw, (inci_name or ""), (primary_cas or ""))

        # Flag composites/mixtures for review (no AI, no compilation).
        blob = raw.lower()
        is_composite = any(tok in blob for tok in ("/", "copolymer", "crosspolymer", "blend", "mixture"))
        if is_composite and status != "orphan":
            status = "review"
            reason = (reason + "; " if reason else "") + "Composite/mixture-like source name"
        # csv.DictReader may use a None key for overflow columns; JSON cannot sort mixed key types.
        safe_payload: dict[str, Any] = {}
        extras: list[Any] = []
        for k, v in (payload or {}).items():
            if k is None:
                # Overflow columns land here as a list
                if v is not None:
                    extras.append(v)
                continue
            safe_payload[str(k)] = v
        if extras:
            safe_payload["__extra__"] = extras

        source_rows.append(
            {
                "key": key,
                "source": source,
                "source_row_id": source_row_id or None,
                "source_row_number": int(source_row_number) if source_row_number is not None else None,
                "source_ref": source_ref or None,
                "content_hash": content_hash,
                "is_composite": bool(is_composite),
                "raw_name": raw,
                "inci_name": (inci_name or "").strip() or None,
                # Keep primary CAS in cas_number for compatibility, but store all for cross-referencing.
                "cas_number": primary_cas or None,
                "cas_numbers_json": json.dumps(cas_numbers, ensure_ascii=False),
                "derived_term": definition or None,
                "derived_variation": variation or None,
                "derived_physical_form": physical_form or None,
                "derived_part": derived_part or None,
                "derived_part_reason": "token_in_raw_name" if derived_part else None,
                "origin": origin,
                "ingredient_category": ingredient_category or None,
                "refinement_level": refinement_level or None,
                "status": status,
                "needs_review_reason": reason,
                "payload_json": json.dumps(safe_payload, ensure_ascii=False, sort_keys=True),
            }
        )

        if write_terms and definition:
            # Seed category for cursoring can use ingredient_category for now (data_builder only).
            rec = normalized_terms.setdefault(
                definition,
                {
                    "term": definition,
                    "seed_category": ingredient_category or None,
                    "botanical_name": "",
                    "inci_name": "",
                    "cas_number": "",
                    "description": "",
                    "ingredient_category": ingredient_category or None,
                    "origin": origin,
                    "refinement_level": refinement_level,
                    "derived_from": "",
                    "ingredient_category_confidence": 60,
                    "origin_confidence": 60,
                    "refinement_confidence": 60,
                    "derived_from_confidence": 0,
                    "overall_confidence": 60,
                    "sources_json": json.dumps({"sources": [source]}, ensure_ascii=False, sort_keys=True),
                },
            )
            # Best-effort identity fields (do not overwrite if already set)
            if cas_number and not rec.get("cas_number"):
                rec["cas_number"] = cas_number
            if inci_name and not rec.get("inci_name"):
                rec["inci_name"] = inci_name

    # CosIng (INCI items)
    cosing_rows: list[dict[str, Any]] = list(_iter_cosing_rows(cosing_path))
    tgsc_rows: list[dict[str, Any]] = list(_iter_tgsc_rows(tgsc_path))

    include_list = include or []
    picked = _pick_rows(
        cosing_rows=cosing_rows,
        tgsc_rows=tgsc_rows,
        sample_size=sample_size,
        seed=seed,
        include=include_list,
    )

    if limit:
        picked = picked[: int(limit)]

    for source, row in picked:
        if source == "cosing":
            inci = (row.get("INCI name") or row.get("INCI Name") or "").strip()
            if not inci:
                continue
            cas_raw = (row.get("CAS No") or "").strip()
            _register_item(source="cosing", raw_name=inci, inci_name=inci, cas_number=cas_raw, payload=row)
        else:
            name = (row.get("common_name") or row.get("name") or "").strip()
            if not name:
                continue
            cas_raw = (row.get("cas_number") or "").strip()
            _register_item(source="tgsc", raw_name=name, inci_name="", cas_number=cas_raw, payload=row)

    inserted_items = database_manager.upsert_source_items(source_rows)
    inserted_terms = 0
    if write_terms:
        inserted_terms = database_manager.upsert_normalized_terms(list(normalized_terms.values()))
    return inserted_items, inserted_terms


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest INCI/TGSC source items into compiler_state.db")
    parser.add_argument("--cosing", default=str(DATA_SOURCES_DIR / "cosing.csv"))
    parser.add_argument("--tgsc", default=str(DATA_SOURCES_DIR / "tgsc_ingredients.csv"))
    parser.add_argument("--limit", type=int, default=0, help="Optional cap (combined across sources)")
    parser.add_argument("--sample", type=int, default=0, help="Random sample size (combined across sources)")
    parser.add_argument("--seed", type=int, default=0, help="Random seed for --sample")
    parser.add_argument("--include", action="append", default=[], help="Force-include rows whose name contains this substring (case-insensitive). Can be repeated.")
    parser.add_argument("--no-terms", action="store_true", help="Do not upsert normalized_terms (items-only ingestion).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    limit = int(args.limit) if args.limit else None
    sample_size = int(args.sample) if args.sample else None
    seed = int(args.seed) if args.seed else None
    cosing_path = Path(args.cosing).resolve()
    tgsc_path = Path(args.tgsc).resolve()
    inserted_items, inserted_terms = ingest_sources(
        cosing_path=cosing_path,
        tgsc_path=tgsc_path,
        limit=limit,
        sample_size=sample_size,
        seed=seed,
        include=list(args.include or []),
        write_terms=not bool(args.no_terms),
    )
    LOGGER.info("Inserted %s new source_items and %s new normalized_terms.", inserted_items, inserted_terms)


if __name__ == "__main__":
    main()

