"""Deterministically derive common names for normalized terms.

Goal:
- Populate `normalized_terms.common_name` only when there is evidence in source data.
- Never guess Latin->English without an anchor.

Evidence sources used:
1) CosIng descriptions that explicitly include a common name, e.g.
   "Vitis Vinifera is a plant material derived from the Grape, Vitis Vinifera L., Vitaceae"
2) CosIng descriptions that include parenthetical common name, e.g.
   "Vitis Vinifera (Grape) Callus Extract is the extract of ..."

This is intentionally conservative and pre-AI.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from collections import Counter
from typing import Optional

from . import database_manager

LOGGER = logging.getLogger(__name__)


_RE_DERIVED_FROM = re.compile(
    r"derived from the\s+(?P<common>[^,]{2,80}),\s+(?P<binomial>[A-Z][a-z]+)\s+(?P<species>[A-Za-z-]{2,})",
)
_RE_PAREN_COMMON = re.compile(
    r"\b(?P<binomial>[A-Z][a-z]+)\s+(?P<species>[A-Za-z-]{2,})\s*\((?P<common>[^)]+)\)",
)
_RE_OF_THE = re.compile(
    r"\bof the\s+(?P<common>[A-Z][^,]{2,80}),\s+(?P<binomial>[A-Z][a-z]+)\s+(?P<species>[A-Za-z-]{2,})",
)


def _clean(s: str) -> str:
    return (s or "").strip().strip(" ,.;:-")


def _soft_title(s: str) -> str:
    t = _clean(s)
    if not t:
        return ""
    # Keep all-caps acronyms and multiword case as-is; otherwise title-case.
    if t.isupper():
        return t
    if t.islower():
        return t.title()
    return t


def _normalize_common_phrase(text: str) -> str:
    """Reduce CosIng-style 'fruit of the kiwi' -> 'Kiwi'."""
    t = _clean(text)
    if not t:
        return ""
    low = t.lower()
    # Strip leading determiners.
    if low.startswith("the "):
        t = t[4:].strip()
        low = t.lower()
    # Common CosIng patterns.
    prefixes = [
        "fruit of the ",
        "fruits of the ",
        "seed of the ",
        "seeds of the ",
        "leaf of the ",
        "leaves of the ",
        "root of the ",
        "roots of the ",
        "flower of the ",
        "flowers of the ",
        "bark of the ",
        "kernel of the ",
        "oil of the ",
        "extract of the ",
        "volatile oil derived from the ",
    ]
    for p in prefixes:
        if low.startswith(p):
            t = t[len(p) :].strip()
            low = t.lower()
            break
    # If still contains " of the ", take the last phrase (best-effort).
    if " of the " in low:
        t = t.rsplit(" of the ", 1)[-1].strip()
    # Strip trailing qualifiers.
    t = re.sub(r"\b(tree|plant|vine|shrub)\b$", "", t, flags=re.IGNORECASE).strip(" ,.-")
    return _soft_title(t)


def _binomial_key(genus: str, species: str) -> str:
    g = _clean(genus).lower()
    sp = _clean(species).lower()
    if not g or not sp:
        return ""
    return f"{g} {sp}"


def build_binomial_common_map() -> dict[str, str]:
    """Return mapping: 'genus species' -> 'Common Name'."""
    database_manager.ensure_tables_exist()
    votes: dict[str, Counter[str]] = {}
    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceCatalogItem.cosing_description)
        for (desc,) in q.yield_per(500):
            d = _clean(desc or "")
            if not d:
                continue

            m = _RE_DERIVED_FROM.search(d)
            if m:
                common = _normalize_common_phrase(m.group("common"))
                key = _binomial_key(m.group("binomial"), m.group("species"))
                if common and key:
                    votes.setdefault(key, Counter())[common] += 3  # strong signal

            m2 = _RE_PAREN_COMMON.search(d)
            if m2:
                common2 = _soft_title(m2.group("common"))
                key2 = _binomial_key(m2.group("binomial"), m2.group("species"))
                if common2 and key2:
                    votes.setdefault(key2, Counter())[common2] += 2

            m3 = _RE_OF_THE.search(d)
            if m3:
                common3 = _normalize_common_phrase(m3.group("common"))
                key3 = _binomial_key(m3.group("binomial"), m3.group("species"))
                if common3 and key3:
                    votes.setdefault(key3, Counter())[common3] += 1

    out: dict[str, str] = {}
    for key, counter in votes.items():
        best, _count = counter.most_common(1)[0]
        out[key] = best
    return out


def _term_binomial_prefix(term: str) -> Optional[str]:
    """Return lowercased 'genus species' if the term begins with a binomial."""
    t = _clean(term)
    m = re.match(r"^([A-Z][a-z]+)\s+([A-Za-z-]{2,})\b", t)
    if not m:
        return None
    return _binomial_key(m.group(1), m.group(2)) or None


def apply_common_names(*, limit: int | None = None) -> dict[str, int]:
    mapping = build_binomial_common_map()
    database_manager.ensure_tables_exist()
    scanned = 0
    updated = 0
    skipped_existing = 0

    with database_manager.get_session() as session:
        q = session.query(database_manager.NormalizedTerm)
        if limit:
            q = q.limit(int(limit))
        for row in q.yield_per(500):
            scanned += 1
            if row.common_name and _clean(row.common_name):
                skipped_existing += 1
                continue

            # Prefer explicit botanical_name if it's a binomial.
            bin_key = _term_binomial_prefix(row.botanical_name or "") or _term_binomial_prefix(row.term or "")
            if not bin_key:
                continue

            common = mapping.get(bin_key)
            if not common:
                continue

            row.common_name = common
            row.common_name_source = "cosing_description_binomial_map"
            updated += 1

    return {"scanned": scanned, "updated": updated, "skipped_existing": skipped_existing, "binomial_map_size": len(mapping)}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Derive deterministic common names for normalized terms")
    p.add_argument("--limit", type=int, default=int(os.getenv("COMMON_NAME_LIMIT", "0")))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    limit = int(args.limit) if int(args.limit or 0) > 0 else None
    stats = apply_common_names(limit=limit)
    LOGGER.info("derived common names: %s", stats)


if __name__ == "__main__":
    main()

