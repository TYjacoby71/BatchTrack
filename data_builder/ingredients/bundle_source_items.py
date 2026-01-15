"""Deterministically bundle SourceItem rows into derived definition clusters.

Goal:
- Create *definition clusters* **post-merge**, driven by `merged_item_forms` (deduped purchasable item identities).
- Each cluster corresponds to a proposed base ingredient definition (canonical term candidate).
- Practically, we assign every merged item-form to a cluster keyed by its base `derived_term`, then
  backfill `source_items.definition_cluster_id` via `source_items.merged_item_id`.
- Produce `source_definitions` (one row per cluster) and annotate each `source_item`
  with `definition_cluster_id`, confidence, and reason.

Important:
- `merged_item_forms` are the post-merge item identities (term + variation + form) with provenance back to source rows.
- This clustering stage groups *those item identities* into term-candidate clusters for the AI to adjudicate.
- Composites remain isolated at the source row level (they do not participate in term clustering).
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


def _cluster_id_for_term(term: str) -> str:
    t = re.sub(r"\s+", " ", _clean(term)).strip().lower()
    return f"term:{t}" if t else ""


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
        # Clear previous definitions (deterministic rebuild)
        session.query(database_manager.SourceDefinition).delete()

        # 1) Build cluster assignment for merged item identities (post-merge).
        mif_q = session.query(database_manager.MergedItemForm)
        if limit and int(limit) > 0:
            mif_q = mif_q.limit(int(limit))
        merged_cluster_by_id: dict[int, str] = {}
        for mif in mif_q.yield_per(2000):
            cid = _cluster_id_for_term(_clean(getattr(mif, "derived_term", "")))
            if cid:
                merged_cluster_by_id[int(mif.id)] = cid

        # 2) Assign each source row to its merged item's cluster (or isolate composites).
        q = session.query(database_manager.SourceItem)
        if limit and int(limit) > 0:
            q = q.limit(int(limit))

        buckets: dict[str, list[database_manager.SourceItem]] = defaultdict(list)
        meta: dict[str, tuple[int, str, str]] = {}

        for item in q.yield_per(2000):
            if bool(getattr(item, "is_composite", False)):
                cluster_id, conf, reason, bkey = f"composite:{item.key}", 40, "composite_item", ""
            else:
                mid = getattr(item, "merged_item_id", None)
                cluster_id = merged_cluster_by_id.get(int(mid)) if mid is not None else ""
                # Fallback to derived_term if merge link is missing.
                if not cluster_id:
                    term_cluster = _cluster_id_for_term(_clean(getattr(item, "derived_term", "")))
                    if term_cluster:
                        cluster_id = term_cluster
                    else:
                        raw_fallback = re.sub(r'\s+', ' ', _clean(getattr(item, 'raw_name', ''))).strip().lower()
                        cluster_id = f"raw:{raw_fallback}"
                conf, reason, bkey = 90, "post_merge_term_cluster", _binomial_key(_clean(getattr(item, "derived_term", "")))

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

