"""Deterministically bundle SourceItem rows into derived definition clusters.

Goal:
- Minimize AI usage by grouping items under high-confidence clusters first.
- Produce `source_definitions` (one row per cluster) and annotate each `source_item`
  with `definition_cluster_id`, confidence, and reason.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter, defaultdict
from typing import Any, Iterable

from . import database_manager

LOGGER = logging.getLogger(__name__)

_AMBIGUOUS_CAS_DERIVED_TERM_THRESHOLD = 5


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _norm_inci(s: str) -> str:
    t = _clean(s).upper()
    t = re.sub(r"\s+", " ", t).strip()
    return t


_CAS_RE = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")


def _cas_list_from_json(s: str) -> list[str]:
    try:
        data = json.loads(s or "[]")
        if isinstance(data, list):
            out = [str(x).strip() for x in data if str(x).strip()]
            # de-dupe preserve order
            seen: set[str] = set()
            uniq: list[str] = []
            for t in out:
                if t in seen:
                    continue
                seen.add(t)
                uniq.append(t)
            return uniq
    except Exception:
        pass
    return []


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


_BINOMIAL_RE = re.compile(r"^\s*([A-Z][a-z]+)\s+([a-z]{2,})(?:\s+([a-z]{2,}))?\b")

_NON_EPITHET = {
    "seed", "kernel", "nut", "leaf", "needle", "cone", "bark", "wood", "flower", "herb", "root", "rhizome", "stem",
    "oil", "extract", "water", "juice", "puree", "purée", "pulp",
    "gum", "resin", "wax", "cera",
    "sp", "ssp", "subsp", "var", "cv", "hybrid", "x",
}

# Tokens that should never be treated as a botanical genus (prevents false "binomial:" clusters
# like "Hydrolyzed collagen" or "Aluminum iron calcium ...").
_NON_GENUS = {
    # processing/modifiers
    "hydrolyzed",
    "hydrogenated",
    "acetylated",
    "oxidized",
    "sulfated",
    "phosphated",
    "refined",
    "unrefined",
    # common chemistry/ions
    "sodium",
    "potassium",
    "calcium",
    "magnesium",
    "zinc",
    "iron",
    "copper",
    "aluminum",
    "ammonium",
    "disodium",
    "dipotassium",
    "tetrasodium",
    "tetrapotassium",
    "trisodium",
    "tripotassium",
    # generic chemical prefixes
    "methyl",
    "ethyl",
    "propyl",
    "butyl",
    "isopropyl",
    "isobutyl",
    "tert",
    "sec",
    "bis",
    "di",
    "tri",
    "tetra",
    "mono",
    # polymers
    "poly",
    "peg",
    "ppg",
}


def _binomial_key(text: str) -> str:
    """Return 'genus species [epithet]' lowercased if present, else ''."""
    s = _clean(text)
    if not s:
        return ""
    m = _BINOMIAL_RE.match(s)
    if not m:
        return ""
    genus = (m.group(1) or "").lower()
    species = (m.group(2) or "").lower()
    epithet = (m.group(3) or "").lower()
    if genus in _NON_GENUS:
        return ""
    # Avoid treating non-botanical "species" tokens as botanical identities.
    if species in _NON_EPITHET:
        return ""
    parts = [genus, species]
    if epithet and epithet not in _NON_EPITHET:
        # Drop accidental repeats: "angustifolia angustifolia"
        if epithet != species:
            parts.append(epithet)
    return " ".join([p for p in parts if p]).strip()


def _cluster_for_item(
    item: database_manager.SourceItem, *, ambiguous_cas: set[str] | None = None
) -> tuple[str, int, str, str]:
    """
    Returns (cluster_id, confidence, reason, botanical_key).

    Confidence tiers (rough):
    - 90: single CAS + INCI present (strong identity)
    - 85: binomial botanical key (genus+species)
    - 75: normalized derived_term fallback
    - 40: composites (kept isolated)
    """
    is_composite = bool(getattr(item, "is_composite", False))
    if is_composite:
        return f"composite:{item.key}", 40, "composite_item", ""

    cas_list = _cas_list_from_json(_clean(getattr(item, "cas_numbers_json", "")))
    if not cas_list:
        cas_list = _cas_tokens(_clean(getattr(item, "cas_number", "")))

    inci = _clean(getattr(item, "inci_name", None))
    inci_norm = _norm_inci(inci) if inci else ""
    ambiguous = ambiguous_cas or set()

    # Prefer single CAS clusters for identity
    if len(cas_list) == 1:
        cas = cas_list[0]
        if cas in ambiguous:
            # Some CAS numbers are effectively "family" identifiers (esp. polymers/mixtures) and
            # will incorrectly collapse many distinct INCI identities into one definition.
            # In those cases, prefer INCI/term identity over CAS.
            if inci_norm:
                return f"inci:{inci_norm}", 82, "ambiguous_cas_use_inci", _binomial_key(
                    _clean(getattr(item, "derived_term", ""))
                )
            term = _clean(getattr(item, "derived_term", "")) or _clean(getattr(item, "raw_name", ""))
            term_norm = re.sub(r"\s+", " ", term).strip().lower()
            return f"term:{term_norm}", 78, "ambiguous_cas_use_term", ""
        if inci_norm:
            return f"cas:{cas}", 90, "single_cas_with_inci", _binomial_key(_clean(getattr(item, "derived_term", "")))
        return f"cas:{cas}", 85, "single_cas", _binomial_key(_clean(getattr(item, "derived_term", "")))

    # Botanical binomial key
    bkey = _binomial_key(_clean(getattr(item, "derived_term", "")))
    if bkey:
        return f"binomial:{bkey}", 85, "binomial_key", bkey

    # INCI-based fallback for chemicals
    if inci_norm:
        return f"inci:{inci_norm}", 80, "inci_identity", ""

    # Last resort: derived_term string
    term = _clean(getattr(item, "derived_term", "")) or _clean(getattr(item, "raw_name", ""))
    term_norm = re.sub(r"\s+", " ", term).strip().lower()
    return f"term:{term_norm}", 75, "derived_term", ""


def _choose_canonical_term(def_names: Iterable[str]) -> str:
    """Pick the most common non-empty definition_display_name."""
    names = [n for n in (_clean(x) for x in def_names) if n]
    if not names:
        return ""
    c = Counter(names)
    # prefer most common; tie-breaker: shortest
    best = sorted(c.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0].casefold()))[0][0]
    return best


def bundle(*, limit: int = 0) -> dict[str, int]:
    database_manager.ensure_tables_exist()
    updated_items = 0
    created_defs = 0

    with database_manager.get_session() as session:
        # Identify CAS numbers that map to many distinct derived terms. These are usually
        # non-unique "family" CAS values (esp. polymers/mixtures), and clustering by CAS
        # would incorrectly merge many distinct INCI identities into one definition.
        cas_to_terms: dict[str, set[str]] = defaultdict(set)
        for item in session.query(database_manager.SourceItem).yield_per(2000):
            if bool(getattr(item, "is_composite", False)):
                continue
            cas_list = _cas_list_from_json(_clean(getattr(item, "cas_numbers_json", "")))
            if not cas_list:
                cas_list = _cas_tokens(_clean(getattr(item, "cas_number", "")))
            if len(cas_list) != 1:
                continue
            term = _clean(getattr(item, "derived_term", "")) or _clean(getattr(item, "raw_name", ""))
            term_norm = re.sub(r"\s+", " ", term).strip().lower()
            if not term_norm:
                continue
            cas_to_terms[cas_list[0]].add(term_norm)
        ambiguous_cas = {
            cas for cas, terms in cas_to_terms.items() if len(terms) >= _AMBIGUOUS_CAS_DERIVED_TERM_THRESHOLD
        }

        # Clear previous definitions (deterministic rebuild)
        session.query(database_manager.SourceDefinition).delete()

        q = session.query(database_manager.SourceItem)
        if limit and int(limit) > 0:
            q = q.limit(int(limit))

        buckets: dict[str, list[database_manager.SourceItem]] = defaultdict(list)
        meta: dict[str, tuple[int, str, str]] = {}

        for item in q.yield_per(1000):
            cluster_id, conf, reason, bkey = _cluster_for_item(item, ambiguous_cas=ambiguous_cas)
            buckets[cluster_id].append(item)
            meta.setdefault(cluster_id, (conf, reason, bkey))

        # Write definition rows + update item cluster fields
        for cluster_id, items in buckets.items():
            conf, reason, bkey = meta.get(cluster_id, (0, "", ""))
            # Aggregate origin/category by mode (ignore blanks)
            origins = [(_clean(i.origin)) for i in items if _clean(i.origin)]
            cats = [(_clean(i.ingredient_category)) for i in items if _clean(i.ingredient_category)]
            origin = Counter(origins).most_common(1)[0][0] if origins else None
            cat = Counter(cats).most_common(1)[0][0] if cats else None

            canonical = _choose_canonical_term([getattr(i, "definition_display_name", "") for i in items]) or None
            cas_members: set[str] = set()
            inci_samples: set[str] = set()
            sample_keys: list[str] = []
            for i in items[:10]:
                sample_keys.append(i.key)
            for i in items:
                for cas in _cas_list_from_json(_clean(getattr(i, "cas_numbers_json", ""))):
                    cas_members.add(cas)
                if _clean(getattr(i, "inci_name", "")):
                    inci_samples.add(_norm_inci(_clean(getattr(i, "inci_name", ""))))

            session.add(
                database_manager.SourceDefinition(
                    cluster_id=cluster_id,
                    canonical_term=canonical,
                    botanical_key=bkey or None,
                    origin=origin,
                    ingredient_category=cat,
                    confidence=int(conf) if conf else None,
                    reason=reason or None,
                    item_count=len(items),
                    sample_item_keys_json=json.dumps(sample_keys, ensure_ascii=False),
                    member_cas_json=json.dumps(sorted(cas_members), ensure_ascii=False),
                    member_inci_samples_json=json.dumps(sorted(list(inci_samples))[:10], ensure_ascii=False),
                )
            )
            created_defs += 1

            for i in items:
                if (i.definition_cluster_id or "") != cluster_id or (i.definition_cluster_confidence or 0) != int(conf):
                    i.definition_cluster_id = cluster_id
                    i.definition_cluster_confidence = int(conf)
                    i.definition_cluster_reason = reason
                    updated_items += 1

    return {"clusters": created_defs, "items_updated": updated_items}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bundle source_items into source_definitions clusters")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    stats = bundle(limit=int(args.limit or 0))
    LOGGER.info("bundled source items: %s", stats)


if __name__ == "__main__":
    main()

