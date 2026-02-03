"""Derive canonical definition terms from merged SourceCatalogItem records.

This is the deterministic "Wave 4" pass, built on top of the merged catalog:

- Prefer TGSC `common_name` for human-friendly term labels *when available*.
- Use variation/form parsing to strip item suffixes (e.g. "seed oil") so the base
  definition term is deduced (e.g. "jojoba").
- Cluster items deterministically into definition identities using strong signals
  (INCI/CAS/EC/botanical), then pick a canonical display term per identity.
- If a clean common term cannot be deduced, fall back to INCI/scientific display
  names (binomial or chemical name) for both the item and the term.

Outputs:
- Upserts `normalized_terms` in Final DB.db (and optionally writes a CSV).
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
from .merge_source_catalog import _norm_inci  # local deterministic normalization
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
    escaped_suffix = re.escape(s).replace(r"\ ", r"\s+")
    pat = re.compile(r"\s+" + escaped_suffix + r"s?$", re.IGNORECASE)
    out = pat.sub("", b).strip(" ,-/")
    return out


_NOISY_COMMON_MARKERS = {
    "replacer",
    "fragrance",
    "perfume",
    "bouquet",
    "supplier",
    "sponsors",
    "articles",
    "notes",
}


def _first_cas(value: str) -> str:
    v = _clean(value)
    m = re.search(r"\b(\d{2,7}-\d{2}-\d)\b", v)
    return m.group(1) if m else ""


def _botanical_key_from_text(text: str) -> str:
    """Extract a normalized binomial key 'genus species' if present."""
    s = _clean(text)
    if not s:
        return ""
    m = re.search(r"\b([A-Z][a-z]+)\s+([a-z]{2,})\b", s)
    if m:
        genus = m.group(1).lower().strip()
        species = m.group(2).lower().strip()
        # Reject obvious non-binomials that are really "common word + part" pairs.
        if genus in {
            "hydrogenated",
            "hydrolyzed",
            "hydroxylated",
            "isomerized",
            "acetylated",
            "decyl",
            "ethyl",
            "isopropyl",
            "propyl",
            "butyl",
            "methyl",
            "peg",
            "ppg",
            "poly",
            "sodium",
            "potassium",
            "calcium",
            "magnesium",
            "zinc",
        }:
            return ""
        if species in {
            "seed",
            "bran",
            "kernel",
            "nut",
            "fruit",
            "berry",
            "leaf",
            "flower",
            "herb",
            "root",
            "bark",
            "wood",
            "cone",
            "needle",
            "stem",
            "sprout",
            "oil",
            "extract",
            "water",
            "juice",
            "wax",
            "butter",
        }:
            return ""
        return f"{genus} {species}".strip()
    return ""


def _botanical_key_from_catalog_item(item: database_manager.SourceCatalogItem) -> str:
    # 1) TGSC botanical_name is the most trustworthy signal.
    tgsc_bot = _botanical_key_from_text(_clean(getattr(item, "tgsc_botanical_name", None)))
    if tgsc_bot:
        return tgsc_bot

    # 2) Derive from INCI only when the INCI looks botanical (avoid "DECYL JOJOBATE" etc).
    inci = _clean(getattr(item, "inci_name", None))
    if not inci:
        return ""
    inci_u = _norm_inci(inci)
    # Must contain a botanical-ish context token (otherwise two-word chemical names will false-match).
    if not re.search(
        r"\b(SEED|LEAF|FLOWER|HERB|ROOT|BARK|WOOD|FRUIT|KERNEL|NUT|CONE|NEEDLE|STEM|RHIZOME|SPROUT|CALLUS|OIL|EXTRACT|WATER|JUICE|WAX|BUTTER)\b",
        inci_u,
    ):
        return ""
    # Exclude obvious leading chemical modifiers.
    first = inci_u.split(" ", 1)[0] if " " in inci_u else inci_u
    if first in {
        "HYDROGENATED",
        "HYDROLYZED",
        "ISOMERIZED",
        "ACETYLATED",
        "PEG-",
        "PPG-",
        "POLY",
        "SODIUM",
        "POTASSIUM",
        "CALCIUM",
        "MAGNESIUM",
        "ZINC",
    }:
        return ""
    # Convert first two INCI tokens into a binomial key.
    parts = inci_u.split()
    if len(parts) < 2:
        return ""
    genus = parts[0].title()
    species = parts[1].lower()
    # Species should not be a generic material token.
    if species in {"oil", "extract", "water", "juice", "wax", "butter", "seed", "leaf", "flower", "herb", "root"}:
        return ""
    # Genus should not be a generic material token.
    if genus.lower() in {"rice", "wheat", "oat", "corn", "sesame", "lavender", "jojoba", "aloe"}:
        # These are common names; botanicals should appear as Latin genus like ORYZA/SESAMUM/LAVANDULA/SIMMONDSIA/ALOE.
        return ""
    key = _botanical_key_from_text(f"{genus} {species}")
    return key or ""


def _clean_base_common_name(text: str) -> str:
    """Clean TGSC-ish common strings down to a stable base identity name."""
    t = _clean(text).strip(" ,\"'")
    if not t:
        return ""
    # Kill obvious junk rows.
    low = t.lower()
    if any(m in low for m in _NOISY_COMMON_MARKERS):
        return ""
    # Drop anything after a comma (often location/marketing).
    if "," in t:
        t = t.split(",", 1)[0].strip()
    # Remove parenthetical clarifiers like "(lavandula luisieri)".
    t = re.sub(r"\([^)]*\)", "", t).strip()
    # Reduce repeated whitespace.
    t = re.sub(r"\s+", " ", t).strip()
    # Drop trailing geo/country qualifiers.
    parts = t.split()
    geo = {"bulgaria", "france", "seville", "spain", "morocco", "tunisia", "italy", "usa"}
    while parts and parts[-1].lower().strip(".") in geo:
        parts = parts[:-1]
    t = " ".join(parts).strip()
    # Reject strings with lots of digits/symbols (not a stable common identity).
    if sum(ch.isdigit() for ch in t) >= 2:
        return ""
    return t


def derive_term_from_common_name(common_name: str, variation: str | None, physical_form: str | None) -> str:
    """
    Use variation/form to back out the base definition from a common/trade item name.
    Example: "jojoba seed oil" + variation "Seed Oil" -> "jojoba"
    """
    cn = _clean_base_common_name(common_name)
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


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def _format_binomial_from_key(bot_key: str) -> str:
    parts = (bot_key or "").split()
    if len(parts) != 2:
        return ""
    return f"{parts[0].title()} {parts[1].lower()}".strip()


def _disambiguate_term(term: str, bot_key: str, used_terms: dict[str, str]) -> str:
    """
    Avoid collapsing distinct identities into one normalized term PK.
    If 'term' already used for a different botanical identity, suffix it.
    """
    t = (term or "").strip()
    if not t:
        return t
    prev = used_terms.get(t)
    if prev is None:
        used_terms[t] = bot_key
        return t
    if prev == bot_key:
        return t
    # Disambiguate.
    bio = _format_binomial_from_key(bot_key)
    if bio:
        t2 = f"{t} ({bio})"
    else:
        t2 = f"{t} ({bot_key or 'variant'})"
    used_terms.setdefault(t2, bot_key)
    return t2


def _pick_canonical_term_for_cluster(
    items: list[database_manager.SourceCatalogItem],
    *,
    used_terms: dict[str, str],
) -> tuple[str, str, str]:
    """
    Returns (term, botanical_key, derived_from).
    botanical_key is best-effort binomial identity key for the cluster (may be empty).
    """
    botanical_keys = sorted({k for k in (_botanical_key_from_catalog_item(i) for i in items) if k})
    cluster_bot = botanical_keys[0] if len(botanical_keys) == 1 else ""

    # IMPORTANT: In the deterministic ingestion system, base terms are derived from the
    # *item parsing* stage (derive_definition_term over the source row display string).
    #
    # This catalog step must NOT invent new term strings (e.g., converting to TGSC common names),
    # otherwise `normalized_terms` can exceed the number of item forms, and the compiler would
    # be handed terms that have no backing items.
    #
    # Therefore: pick a canonical term by applying `derive_definition_term` to the best available
    # representative display string (prefer INCI when present).
    rep = None
    for it in items:
        inci = _clean(getattr(it, "inci_name", None))
        if inci:
            rep = inci
            break
    if rep is None:
        rep = _clean(getattr(items[0], "common_name", None)) or _clean(getattr(items[0], "inci_name", None))

    derived = derive_definition_term(rep or "")
    if derived:
        term = _disambiguate_term(derived, cluster_bot or derived.lower(), used_terms)
        return term, cluster_bot, "derived_from_catalog_display"

    # Fallbacks (should be rare).
    if cluster_bot:
        term = _format_binomial_from_key(cluster_bot)
        term = _disambiguate_term(term, cluster_bot, used_terms)
        return term, cluster_bot, "botanical_binomial"

    any_name = _clean(getattr(items[0], "inci_name", None)) or _clean(getattr(items[0], "common_name", None))
    term = _disambiguate_term(any_name or "Unknown", any_name.lower(), used_terms)
    return term, "", "unknown"


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

    # Load catalog items (filtered)
    catalog_items: list[database_manager.SourceCatalogItem] = []
    scanned = 0

    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceCatalogItem)
        for item in q.yield_per(500):
            if limit and scanned >= int(limit):
                break
            scanned += 1

            display_name = _clean(getattr(item, "common_name", None)) or _clean(getattr(item, "inci_name", None))
            if not display_name:
                continue
            if not _include_ok(display_name):
                continue

            catalog_items.append(item)

    if not catalog_items:
        return {"catalog_scanned": scanned, "clusters": 0, "terms_rows_built": 0, "terms_inserted": 0}

    # ----------------------------
    # Wave 4a: deterministic identity clustering
    # ----------------------------
    uf = _UnionFind(len(catalog_items))
    inci_seen: dict[str, int] = {}
    cas_seen: dict[str, int] = {}
    ec_seen: dict[str, int] = {}
    bot_seen: dict[str, int] = {}

    for idx, it in enumerate(catalog_items):
        inci = _clean(getattr(it, "inci_name", None))
        cas = _first_cas(_clean(getattr(it, "cas_number", None)))
        ec = _clean(getattr(it, "ec_number", None))
        bot = _botanical_key_from_catalog_item(it)

        if inci:
            key = _norm_inci(inci)
            if key in inci_seen:
                uf.union(idx, inci_seen[key])
            else:
                inci_seen[key] = idx
        if cas:
            if cas in cas_seen:
                uf.union(idx, cas_seen[cas])
            else:
                cas_seen[cas] = idx
        if ec:
            if ec in ec_seen:
                uf.union(idx, ec_seen[ec])
            else:
                ec_seen[ec] = idx
        if bot:
            if bot in bot_seen:
                uf.union(idx, bot_seen[bot])
            else:
                bot_seen[bot] = idx

    clusters: dict[int, list[int]] = {}
    for i in range(len(catalog_items)):
        r = uf.find(i)
        clusters.setdefault(r, []).append(i)

    # ----------------------------
    # Wave 4b: pick canonical display term per identity cluster
    # ----------------------------
    rows: list[dict[str, Any]] = []
    used_terms: dict[str, str] = {}
    for root, indices in clusters.items():
        cluster_items = [catalog_items[i] for i in indices]
        term, bot_key, derived_from = _pick_canonical_term_for_cluster(cluster_items, used_terms=used_terms)

        # Use any representative display to infer origin/category/refinement deterministically.
        rep = cluster_items[0]
        rep_display = _clean(getattr(rep, "common_name", None)) or _clean(getattr(rep, "inci_name", None)) or term

        origin = infer_origin(rep_display)
        ingredient_category = infer_primary_category(term, origin, rep_display)
        refinement_level = infer_refinement(term, rep_display)
        seed_category = ingredient_category or None

        botanical = _format_binomial_from_key(bot_key) if bot_key else (_clean(getattr(rep, "tgsc_botanical_name", None)) or None)

        # Representative identifiers
        rep_inci = _clean(getattr(rep, "inci_name", None)) or None
        rep_cas = _first_cas(_clean(getattr(rep, "cas_number", None))) or None

        sources = {
            "cluster_size": len(cluster_items),
            "cluster_keys": {
                "cas": sorted({k for k in (_first_cas(_clean(getattr(i, "cas_number", None))) for i in cluster_items) if k})[:10],
                "ec": sorted({k for k in (_clean(getattr(i, "ec_number", None)) for i in cluster_items) if k})[:10],
                "botanical": sorted({k for k in (_botanical_key_from_catalog_item(i) for i in cluster_items) if k})[:10],
                "inci_samples": sorted({_norm_inci(_clean(getattr(i, "inci_name", None))) for i in cluster_items if _clean(getattr(i, "inci_name", None))})[:5],
            },
            "common_name_samples": sorted({(_clean(getattr(i, "common_name", None)) or "") for i in cluster_items if _clean(getattr(i, "common_name", None))})[:5],
            "catalog_key_samples": sorted({i.key for i in cluster_items if getattr(i, "key", None)})[:5],
        }
        sources_json = json.dumps(sources, ensure_ascii=False, sort_keys=True)

        rows.append(
            {
                "term": term,
                "seed_category": seed_category,
                "botanical_name": botanical,
                "inci_name": rep_inci,
                "cas_number": rep_cas,
                "description": _clean(getattr(rep, "cosing_description", None)) or _clean(getattr(rep, "tgsc_description", None)) or None,
                "ingredient_category": ingredient_category,
                "origin": origin,
                "refinement_level": refinement_level,
                "derived_from": derived_from,
                "overall_confidence": 80 if derived_from == "tgsc_base_common_name" else 70,
                "sources_json": sources_json,
            }
        )

    inserted = 0
    if not no_db:
        # Guardrail: only upsert terms that already exist from item ingestion.
        # This prevents `normalized_terms` from exceeding the item universe.
        with database_manager.get_session() as session:
            existing_terms = {r[0] for r in session.query(database_manager.NormalizedTerm.term).all()}
        rows = [r for r in rows if (r.get("term") or "").strip() in existing_terms]
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
        "clusters": len(clusters),
        "terms_rows_built": len(rows),
        "terms_inserted": int(inserted),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Derive canonical normalized_terms from source_catalog_items")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--include", action="append", default=[], help="Only process items containing this substring (repeatable)")
    p.add_argument("--no-db", action="store_true", help="Do not write to Final DB.db")
    p.add_argument("--csv-out", default="", help="Optional CSV output path")
    p.add_argument("--show", type=int, default=0, help="Print up to N derived term rows to stdout (debug)")
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
    if int(args.show or 0) > 0 and csv_out and csv_out.exists():
        try:
            with csv_out.open("r", encoding="utf-8", newline="") as handle:
                r = csv.DictReader(handle)
                for idx, row in enumerate(r):
                    if idx >= int(args.show):
                        break
                    print(f"{idx+1}. {row.get('term')}  [{row.get('derived_from')}]  bot={row.get('botanical_name')}")
        except Exception:
            return


if __name__ == "__main__":
    main()

