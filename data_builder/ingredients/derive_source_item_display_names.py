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
    # NOTE: avoid broad substring checks like "POLY" which false-positive botanicals (e.g. POLYGONUM).
    if any(tok in n.upper() for tok in ("PEG-", "PPG-", "QUATERNIUM-", "POLYQUATERNIUM", "COPOLYMER", "CROSSPOLYMER", "POLYMER")):
        return True
    if sum(ch.isdigit() for ch in n) >= 3:
        return True
    return False


def _soft_title_common(s: str) -> str:
    """Title-case a plain common name; keep acronyms/digit-heavy strings unchanged."""
    t = _clean(s)
    if not t:
        return ""
    # Preserve obviously non-human labels.
    if sum(ch.isdigit() for ch in t) >= 2:
        return t
    if t.isupper() or t.islower():
        return t.title()
    return t


def _clean_tgsc_common_base(raw: str) -> str:
    """
    Reduce TGSC-style item names down to a stable base *common name* candidate.
    Examples:
    - "lavender absolute bulgaria," -> "lavender"
    - "aorta extract," -> "aorta"
    """
    t = _clean(raw).strip(" ,\"'")
    if not t:
        return ""
    # Drop anything after a comma (TGSC often adds location/marketing after commas).
    if "," in t:
        t = t.split(",", 1)[0].strip()
    # Remove parenthetical clarifiers.
    t = re.sub(r"\([^)]*\)", "", t).strip()
    t = re.sub(r"\s+", " ", t).strip()
    # Drop trailing geo/country qualifiers.
    parts = t.split()
    geo = {
        "bulgaria",
        "france",
        "spain",
        "italy",
        "morocco",
        "tunisia",
        "usa",
        "u.s.a.",
        "uk",
        "u.k.",
    }
    while parts and parts[-1].lower().strip(".") in geo:
        parts = parts[:-1]
    t = " ".join(parts).strip()
    # Drop common trailing variation tokens even when they aren't the parsed variation.
    for token in ("absolute", "concrete", "extract", "oil", "water", "hydrosol", "juice", "powder", "pulp"):
        t = re.sub(rf"\s+{re.escape(token)}\s*$", "", t, flags=re.IGNORECASE).strip(" ,-/")
    # Reject noisy strings.
    if not t or sum(ch.isdigit() for ch in t) >= 2:
        return ""
    return t.strip()


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
    # Item-first cross-ref: allow CosIng source_items to inherit a stable TGSC common name
    # when they share a strong identity token (CAS). This does NOT merge rows; it only
    # improves maker-facing display names deterministically.
    cas_to_best_tgsc_common_base: dict[str, str] = {}
    # NOTE: INCI->common overlay is intentionally NOT used here because it can produce
    # incorrect mappings when TGSC rows get merged onto an INCI string loosely.
    # We only trust common_name when it was obtained via strong identity linkage (CAS).

    with database_manager.get_session() as session:
        # Build CAS -> best TGSC base common name candidate.
        for row in (
            session.query(database_manager.SourceItem)
            .filter(database_manager.SourceItem.source == "tgsc")
            .yield_per(2000)
        ):
            raw = _clean(getattr(row, "raw_name", ""))
            if not raw:
                continue
            cas_list: list[str] = []
            try:
                cas_list = json.loads(getattr(row, "cas_numbers_json", None) or "[]")
                if not isinstance(cas_list, list):
                    cas_list = []
            except Exception:
                cas_list = []
            if not cas_list:
                cas_list = _cas_tokens(_clean(getattr(row, "cas_number", "")))
            if not cas_list:
                continue
            base = _clean_tgsc_common_base(raw)
            if not base:
                continue
            # Prefer shorter, cleaner bases per CAS.
            for cas in cas_list:
                cur_base = _clean(cas_to_best_tgsc_common_base.get(cas, ""))
                if (not cur_base) or (len(base) < len(cur_base)):
                    cas_to_best_tgsc_common_base[cas] = base

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
                # Prefer TGSC source_items-derived common base name when available.
                # This is safer than catalog common_name for botanicals because it is closer
                # to the actual TGSC item naming, but we still only use it as a *base* label.
                tgsc_base = _clean(cas_to_best_tgsc_common_base.get(cas, ""))
                if tgsc_base:
                    common = tgsc_base
                    break

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
            # 1) INCI label for chemical-like identities (keep the INCI/chemical identity stable)
            # 2) derived_term (parser): this is the canonical definition label we want to carry
            # 3) catalog common_name (stripped of variation suffix) as a fallback only
            # 4) raw_name (last resort)
            derived_term = _clean(row.derived_term)
            base = ""
            if _clean(row.inci_name):
                inci_label = _clean(row.inci_name)
                if _is_chemical_like(inci_label):
                    base = inci_label
                elif derived_term:
                    # Prefer a stable TGSC common base name when available (and non-chemical).
                    # This is how we let a CAS-linked TGSC common name drive the maker-facing
                    # definition label instead of forcing a binomial/scientific fallback.
                    if common and not _is_chemical_like(derived_term):
                        base = _soft_title_common(common)
                    else:
                        base = derived_term
                else:
                    base = inci_label
            elif derived_term:
                if common and not _is_chemical_like(derived_term):
                    base = _soft_title_common(common)
                else:
                    base = derived_term
            elif common:
                base = _soft_title_common(_base_from_common_name(common, variation))
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

