"""Derive maker-facing display names for SourceItem rows (deterministic).

This is a post-pass over `source_items` that produces:
- definition_display_name: best available base label for the definition identity
- item_display_name: definition_display_name + variation (when applicable)

Key idea:
- `raw_name` is source truth (often INCI and sometimes composite/mixture).
- Display names should be usable in the app/library.
- For "chemical-like" items (including numeric-leading), we bypass variation composition and
  keep the INCI/chemical name as both definition+item display.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from typing import Any

from . import database_manager

LOGGER = logging.getLogger(__name__)


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _norm_inci(s: str) -> str:
    t = _clean(s).upper()
    t = re.sub(r"\s+", " ", t).strip()
    return t


_CAS_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")


def _cas_tokens(s: str) -> list[str]:
    v = _clean(s)
    if not v:
        return []
    toks = _CAS_RE.findall(v)
    seen: set[str] = set()
    out: list[str] = []
    for t in toks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _is_chemical_like(name: str) -> bool:
    """Heuristic: numeric-leading or lots of digits/hyphens indicates chemical/INCI-style identity."""
    n = _clean(name)
    if not n:
        return False
    if n[0].isdigit():
        return True
    # Common INCI chemical-ish patterns
    if any(tok in n.upper() for tok in ("PEG-", "PPG-", "QUATERNIUM-", "POLY", "COPOLYMER", "CROSSPOLYMER")):
        return True
    if sum(ch.isdigit() for ch in n) >= 3:
        return True
    return False


def _truncate(s: str, max_len: int = 80) -> str:
    t = _clean(s)
    if len(t) <= max_len:
        return t
    return t[: max(0, max_len - 1)].rstrip() + "…"


def _compose_item_name(base: str, variation: str | None) -> str:
    b = _clean(base)
    v = _clean(variation)
    if not b:
        return ""
    if not v:
        return b
    if b.lower().endswith(v.lower()):
        return b
    return f"{b} {v}".strip()


def _base_from_common_name(common_name: str, variation: str | None) -> str:
    """Strip a trailing variation phrase from a common name when possible."""
    cn = _clean(common_name).strip(" ,")
    if not cn:
        return ""
    v = _clean(variation)
    # Always remove common variation tokens at end (even if they don't match current variation).
    # This prevents cases like "peppermint absolute" becoming the base label for an Extract item.
    trailing_variations = [
        v,
        "absolute",
        "concrete",
        "essential oil",
        "oil",
        "extract",
        "water",
        "hydrosol",
        "juice",
        "puree",
        "purée",
        "pulp",
    ]
    out = cn
    for token in [t for t in trailing_variations if t]:
        pat = re.compile(rf"\s+{re.escape(token)}\s*$", re.IGNORECASE)
        out2 = pat.sub("", out).strip(" ,-/")
        if out2 and out2 != out:
            out = out2
    return out or cn


def _tokenize(s: str) -> set[str]:
    t = _clean(s).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    parts = {p for p in t.split() if p and len(p) >= 3}
    # drop generic noise words
    parts -= {"the", "and", "with", "for", "from", "oil", "extract", "absolute", "concrete", "water", "juice", "puree", "pulp"}
    return parts


def derive_display_names(*, limit: int = 0) -> dict[str, int]:
    """Populate display name fields for source_items using source_catalog_items as cross-reference."""
    database_manager.ensure_tables_exist()
    updated = 0
    scanned = 0

    # Build cross-ref maps from merged catalog.
    cas_to_common: dict[str, str] = {}
    cas_to_inci: dict[str, str] = {}
    # NOTE: INCI->common overlay is intentionally NOT used here because it can produce
    # incorrect mappings when TGSC rows get merged onto an INCI string loosely.
    # We only trust common_name when it was obtained via strong identity linkage (CAS).

    with database_manager.get_session() as session:
        for item in session.query(database_manager.SourceCatalogItem).yield_per(1000):
            inci = _clean(getattr(item, "inci_name", None))
            common = _clean(getattr(item, "common_name", None))
            cas = _clean(getattr(item, "cas_number", None))
            if cas:
                cas_to_common.setdefault(cas, common)
                cas_to_inci.setdefault(cas, inci)

        q = session.query(database_manager.SourceItem)
        if limit and int(limit) > 0:
            q = q.limit(int(limit))

        for row in q.yield_per(1000):
            scanned += 1
            raw = _clean(row.raw_name)
            variation = _clean(row.derived_variation) or None

            # Default base label candidates
            cas_list: list[str] = []
            try:
                cas_list = json.loads(row.cas_numbers_json or "[]")
                if not isinstance(cas_list, list):
                    cas_list = []
            except Exception:
                cas_list = []
            if not cas_list:
                # fall back to any CAS tokens in cas_number field
                cas_list = _cas_tokens(_clean(row.cas_number))

            inci_norm = _norm_inci(_clean(row.inci_name)) if _clean(row.inci_name) else ""

            # Pull best catalog common_name if we can.
            common = ""
            for cas in cas_list:
                c = _clean(cas_to_common.get(cas, ""))
                if c:
                    # Guardrail: CAS can be shared/ambiguous for natural materials.
                    # If this SourceItem has an INCI name, only trust the catalog common_name
                    # when the catalog INCI for that CAS matches this INCI.
                    if inci_norm:
                        cat_inci = _norm_inci(_clean(cas_to_inci.get(cas, ""))) if _clean(cas_to_inci.get(cas, "")) else ""
                        if cat_inci and cat_inci != inci_norm:
                            continue
                    else:
                        # TGSC-only rows have no INCI; require at least one meaningful token overlap
                        # between the source raw name and the candidate common name.
                        if _tokenize(raw).isdisjoint(_tokenize(c)):
                            continue
                    common = c
                    break

            # Base label priority:
            # 1) catalog common_name (stripped of variation suffix)
            # 2) INCI label for chemical-like identities; otherwise derived_term
            # 3) derived_term (parser) / raw_name fallback
            # 4) raw_name (last resort)
            derived_term = _clean(row.derived_term)
            base = ""
            if common:
                base = _base_from_common_name(common, variation)
            elif _clean(row.inci_name):
                # Keep INCI label as base for chemical-like; for botanicals prefer derived_term.
                inci_label = _clean(row.inci_name)
                if _is_chemical_like(inci_label):
                    base = inci_label
                else:
                    base = derived_term or inci_label
            elif derived_term:
                base = derived_term
            else:
                base = raw

            # Composite: keep maker display short and force review.
            if bool(getattr(row, "is_composite", False)):
                base = _truncate(base, 60)
                item_name = _truncate(raw, 80)
            else:
                # Chemical-like: bypass (definition == item name).
                if _is_chemical_like(base) or _is_chemical_like(raw):
                    item_name = base
                else:
                    item_name = _compose_item_name(base, variation)

            base = base.strip()
            item_name = item_name.strip()

            # Only update if changed (avoid dirtying rows repeatedly)
            if (_clean(row.definition_display_name) != base) or (_clean(row.item_display_name) != item_name):
                row.definition_display_name = base or None
                row.item_display_name = item_name or None
                updated += 1

    return {"scanned": scanned, "updated": updated}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Derive definition/item display names for source_items")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    stats = derive_display_names(limit=int(args.limit or 0))
    LOGGER.info("derived display names: %s", stats)


if __name__ == "__main__":
    main()

