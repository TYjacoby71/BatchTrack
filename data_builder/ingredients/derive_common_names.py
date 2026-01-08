"""Deterministically populate NormalizedTerm.common_name when evidence exists.

Goals (from your transcript):
- No AI, no external mapping list required.
- Never guess Latin -> English without evidence.
- Use existing sources already in the DB:
  - TGSC common_name (via CAS/EC identity merge)
  - TGSC botanical_name matches (binomial)
  - CosIng description text patterns ("derived from the Grape, Vitis vinifera ...")
- For part-split terms ("Vitis vinifera Seed"), apply part suffix when base common exists.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from . import database_manager


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _soft_title_common(s: str) -> str:
    t = _clean(s)
    if not t:
        return ""
    # keep all-caps chem strings unchanged
    if sum(ch.isdigit() for ch in t) >= 2:
        return t
    if t.islower() or t.isupper():
        return t.title()
    return t


_BINOMIAL_RE = re.compile(r"^\s*([A-Z][a-z]+)\s+([a-z]{2,})\b")

# CosIng pattern: "derived from the Grape, Vitis vinifera ..."
_COSING_DERIVED_RE = re.compile(
    r"derived\s+from\s+the\s+(?P<common>[^,;()]{2,60})\s*,\s*(?P<binomial>[A-Z][a-z]+\s+[a-z]{2,})",
    re.IGNORECASE,
)

# CosIng/TGSC often embed common name in parentheses: "Vitis vinifera (grape)"
_BINOMIAL_PAREN_RE = re.compile(r"\b(?P<binomial>[A-Z][a-z]+\s+[a-z]{2,})\s*\((?P<common>[^)]+)\)")


def _binomial_key(term: str) -> str:
    m = _BINOMIAL_RE.match(_clean(term))
    if not m:
        return ""
    return f"{m.group(1).lower()} {m.group(2).lower()}".strip()


def derive_common_names() -> dict[str, int]:
    database_manager.ensure_tables_exist()
    scanned = 0
    updated = 0
    mappings_built = 0

    # Build binomial -> common mapping candidates
    binomial_to_common: dict[str, tuple[str, str]] = {}

    with database_manager.get_session() as session:
        # 1) From CosIng description text in source_catalog_items
        for row in session.query(database_manager.SourceCatalogItem).yield_per(5000):
            desc = _clean(getattr(row, "cosing_description", None))
            if not desc:
                continue
            m = _COSING_DERIVED_RE.search(desc)
            if not m:
                # Fall back: capture "Genus species (common)" occurrences.
                for mm in _BINOMIAL_PAREN_RE.finditer(desc):
                    common = _soft_title_common(mm.group("common"))
                    binom = _clean(mm.group("binomial"))
                    key = _binomial_key(binom)
                    if key and common:
                        binomial_to_common.setdefault(key, (common, "cosing_description_paren"))
                continue
            common = _soft_title_common(m.group("common"))
            binom = _clean(m.group("binomial"))
            key = _binomial_key(binom)
            if not key or not common:
                continue
            # Prefer first-seen mapping per binomial (deterministic)
            binomial_to_common.setdefault(key, (common, "cosing_description"))

        # 2) From TGSC botanical_name fields when present
        for row in session.query(database_manager.SourceCatalogItem).yield_per(5000):
            tgsc_common = _soft_title_common(_clean(getattr(row, "common_name", None)))
            bname = _clean(getattr(row, "tgsc_botanical_name", None))
            key = _binomial_key(bname)
            if key and tgsc_common:
                binomial_to_common.setdefault(key, (tgsc_common, "tgsc_botanical_name"))

        mappings_built = len(binomial_to_common)

        # Apply to normalized_terms (fill-only)
        terms = session.query(database_manager.NormalizedTerm).yield_per(5000)
        for t in terms:
            scanned += 1
            if _clean(getattr(t, "common_name", None)):
                continue

            term = _clean(getattr(t, "term", None))
            if not term:
                continue

            # Handle part-split terms: "Genus species Part"
            parts = term.split()
            base = ""
            suffix = ""
            if len(parts) >= 2 and _BINOMIAL_RE.match(" ".join(parts[:2])):
                base = " ".join(parts[:2])
                if len(parts) >= 3:
                    suffix = " ".join(parts[2:]).strip()

            key = _binomial_key(base or term)
            if key and key in binomial_to_common:
                base_common, src = binomial_to_common[key]
                cn = base_common
                if suffix:
                    cn = f"{base_common} {suffix}".strip()
                    src = src + "+part_suffix"
                t.common_name = cn
                t.common_name_source = src
                t.normalized_at = datetime.utcnow()
                updated += 1
                continue

            # CAS-linked TGSC common name for non-binomials
            cas = _clean(getattr(t, "cas_number", None))
            if cas:
                cat = session.get(database_manager.SourceCatalogItem, f"cas:{cas}")
                if cat is not None:
                    tgsc_common = _soft_title_common(_clean(getattr(cat, "common_name", None)))
                    if tgsc_common:
                        t.common_name = tgsc_common
                        t.common_name_source = "tgsc_common_name(cas)"
                        t.normalized_at = datetime.utcnow()
                        updated += 1

    return {"scanned": scanned, "updated": updated, "binomial_mappings": mappings_built}

