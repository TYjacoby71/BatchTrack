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
from .item_parser import derive_definition_term, infer_origin, infer_primary_category, infer_refinement

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
    # Some rows contain multiple CAS values separated by commas.
    first = v.split(",")[0].strip()
    return first


def _iter_cosing_rows(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def _iter_tgsc_rows(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
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

        status = "linked" if definition else "orphan"
        reason = None
        if not definition:
            reason = "Unable to derive definition term from source item"

        key = _sha_key(source, raw, (inci_name or ""), (cas_number or ""))
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
                "raw_name": raw,
                "inci_name": (inci_name or "").strip() or None,
                "cas_number": (cas_number or "").strip() or None,
                "derived_term": definition or None,
                "origin": origin,
                "ingredient_category": ingredient_category or None,
                "refinement_level": refinement_level or None,
                "status": status,
                "needs_review_reason": reason,
                "payload_json": json.dumps(safe_payload, ensure_ascii=False, sort_keys=True),
            }
        )

        if definition:
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
            cas = _first_cas((row.get("CAS No") or "").strip())
            _register_item(source="cosing", raw_name=inci, inci_name=inci, cas_number=cas, payload=row)
        else:
            name = (row.get("common_name") or row.get("name") or "").strip()
            if not name:
                continue
            cas = _first_cas((row.get("cas_number") or "").strip())
            _register_item(source="tgsc", raw_name=name, inci_name="", cas_number=cas, payload=row)

    inserted_items = database_manager.upsert_source_items(source_rows)
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
    )
    LOGGER.info("Inserted %s new source_items and %s new normalized_terms.", inserted_items, inserted_terms)


if __name__ == "__main__":
    main()

