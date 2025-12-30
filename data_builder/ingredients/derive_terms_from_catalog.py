"""Derive canonical definition terms from merged SourceCatalogItem records.

This is the deterministic "Wave 4" pass, built on top of the merged catalog:

- Prefer TGSC `common_name` for human-friendly term labels *when available*.
- If the item name includes a clear variation/form (e.g. "seed oil"), strip it to
  deduce the base definition term (e.g. "jojoba").
- If common_name is missing or not safely reducible, fall back to INCI/scientific
  display names (binomial or chemical name) for both the item and the term.

Outputs:
- Upserts `normalized_terms` in compiler_state.db (and optionally writes a CSV).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional

from . import database_manager
from .item_parser import (
    derive_definition_term,
    extract_variation_and_physical_form,
    infer_origin,
    infer_primary_category,
    infer_refinement,
)

LOGGER = logging.getLogger(__name__)


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _soft_title(s: str) -> str:
    """
    Title-case only when the string is clearly a plain common name.
    Never .title() binomials because it would uppercase the species.
    """
    t = _clean(s)
    if not t:
        return ""
    # Preserve parser output for binomials / chemical-like names.
    if re.match(r"^[A-Z][a-z]+ [a-z]{2,}\b", t):
        return t
    if t.isupper() or t.islower():
        return t.title()
    return t


def _strip_suffix_phrase(base: str, suffix: str) -> str:
    b = _clean(base)
    s = _clean(suffix)
    if not b or not s:
        return b
    # Match " <suffix>" at end, case-insensitive, with flexible whitespace.
    pat = re.compile(rf"\s+{re.escape(s).replace(r'\ ', r'\s+')}s?$", re.IGNORECASE)
    out = pat.sub("", b).strip(" ,-/")
    return out


def derive_term_from_common_name(common_name: str, variation: str | None, physical_form: str | None) -> str:
    """
    Use variation/form to back out the base definition from a common/trade item name.
    Example: "jojoba seed oil" + variation "Seed Oil" -> "jojoba"
    """
    cn = _clean(common_name)
    if not cn:
        return ""
    term = cn
    if variation:
        term = _strip_suffix_phrase(term, variation)
    # Physical form is often redundant with variation, but handle names like "Lavender Oil".
    if physical_form:
        term2 = _strip_suffix_phrase(term, physical_form)
        if term2:
            term = term2
    return term.strip()


def _pick_best_term_for_catalog_item(item: database_manager.SourceCatalogItem) -> tuple[str, str]:
    """
    Returns (term, derived_from) where derived_from describes the decision.
    """
    common_name = _clean(getattr(item, "common_name", None))
    inci_name = _clean(getattr(item, "inci_name", None))

    # Decide which name to parse for variation/form.
    display_name = common_name or inci_name
    variation, physical_form = extract_variation_and_physical_form(display_name)

    if common_name:
        deduced = derive_term_from_common_name(common_name, variation, physical_form)
        if deduced:
            return _soft_title(deduced), "tgsc_common_name_minus_variation"
        return _soft_title(common_name), "tgsc_common_name"

    if inci_name:
        return derive_definition_term(inci_name), "inci_name"

    # Should be extremely rare (catalog key-only).
    return "", "unknown"


def build_terms_from_catalog(
    *,
    csv_out: Optional[Path] = None,
    limit: Optional[int] = None,
    include: Optional[list[str]] = None,
    no_db: bool = False,
) -> dict[str, int]:
    include_tokens = [t.strip().lower() for t in (include or []) if (t or "").strip()]
    database_manager.ensure_tables_exist()

    def _include_ok(text: str) -> bool:
        if not include_tokens:
            return True
        tl = (text or "").lower()
        return any(tok in tl for tok in include_tokens)

    rows: list[dict[str, Any]] = []
    scanned = 0
    skipped = 0

    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceCatalogItem)
        for item in q.yield_per(500):
            if limit and scanned >= int(limit):
                break
            scanned += 1

            display_name = _clean(item.common_name) or _clean(item.inci_name)
            if not display_name:
                skipped += 1
                continue
            if not _include_ok(display_name):
                continue

            term, derived_from = _pick_best_term_for_catalog_item(item)
            if not term:
                skipped += 1
                continue

            origin = infer_origin(display_name)
            ingredient_category = infer_primary_category(term, origin, display_name)
            refinement_level = infer_refinement(term, display_name)

            # Seed category is used elsewhere as a coarse bucket; keep aligned to ingredient_category.
            seed_category = ingredient_category or None

            # Botanical hint: prefer TGSC botanical_name; else keep the parser's binomial if it is one.
            botanical = _clean(getattr(item, "tgsc_botanical_name", None))
            if not botanical:
                parsed = derive_definition_term(_clean(item.inci_name))
                botanical = parsed if re.match(r"^[A-Z][a-z]+ [a-z]{2,}\b", parsed) else ""

            sources = {
                "catalog_key": item.key,
                "common_name": _clean(item.common_name) or None,
                "inci_name": _clean(item.inci_name) or None,
                "cas_number": _clean(item.cas_number) or None,
                "ec_number": _clean(item.ec_number) or None,
                "cosing_update_date": _clean(getattr(item, "cosing_update_date", None)) or None,
                "tgsc_url": _clean(getattr(item, "tgsc_url", None)) or None,
            }
            sources_json = json.dumps(sources, ensure_ascii=False, sort_keys=True)

            rows.append(
                {
                    "term": term,
                    "seed_category": seed_category,
                    "botanical_name": botanical or None,
                    "inci_name": _clean(item.inci_name) or None,
                    "cas_number": _clean(item.cas_number) or None,
                    "description": _clean(item.cosing_description) or _clean(getattr(item, "tgsc_description", None)) or None,
                    "ingredient_category": ingredient_category,
                    "origin": origin,
                    "refinement_level": refinement_level,
                    "derived_from": derived_from,
                    "overall_confidence": 70,
                    "sources_json": sources_json,
                }
            )

    inserted = 0
    if not no_db:
        inserted = database_manager.upsert_normalized_terms(rows)

    if csv_out:
        csv_out.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "term",
            "seed_category",
            "botanical_name",
            "inci_name",
            "cas_number",
            "description",
            "ingredient_category",
            "origin",
            "refinement_level",
            "derived_from",
            "overall_confidence",
            "sources_json",
        ]
        with csv_out.open("w", encoding="utf-8", newline="") as handle:
            w = csv.DictWriter(handle, fieldnames=fieldnames)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    return {
        "catalog_scanned": scanned,
        "terms_rows_built": len(rows),
        "terms_inserted": int(inserted),
        "terms_skipped": skipped,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Derive canonical normalized_terms from source_catalog_items")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--include", action="append", default=[], help="Only process items containing this substring (repeatable)")
    p.add_argument("--no-db", action="store_true", help="Do not write to compiler_state.db")
    p.add_argument("--csv-out", default="", help="Optional CSV output path")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    csv_out = Path(args.csv_out).resolve() if str(args.csv_out or "").strip() else None
    limit = int(args.limit) if args.limit else None
    stats = build_terms_from_catalog(
        csv_out=csv_out,
        limit=limit,
        include=list(args.include or []),
        no_db=bool(args.no_db),
    )
    LOGGER.info("derived terms from catalog: %s", stats)


if __name__ == "__main__":
    main()

