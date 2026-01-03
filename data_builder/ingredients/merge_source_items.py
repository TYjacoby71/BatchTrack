"""Deterministically merge duplicate item-forms produced by ingestion.

This is an ingestion-stage merge (non-AI):
- It does NOT delete source_items (provenance stays).
- It creates a deduped table of item-forms (one row per derived_term+variation+form)
  and links each SourceItem row to its merged item id.

Use case:
- When CosIng and TGSC have the same item-form (same derived_term + derived_variation +
  derived_physical_form), we want a single merged item record that aggregates all
  source-backed attributes (CAS/INCI/spec blobs/etc.).
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter, defaultdict
from typing import Any

from . import database_manager

LOGGER = logging.getLogger(__name__)


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _norm(s: str) -> str:
    return _clean(s).lower()


def merge_source_items(*, limit: int = 0) -> dict[str, int]:
    database_manager.ensure_tables_exist()
    created = 0
    updated_links = 0

    with database_manager.get_session() as session:
        # Clear previous merged rows (deterministic rebuild)
        session.query(database_manager.MergedItemForm).delete()

        q = session.query(database_manager.SourceItem).filter(database_manager.SourceItem.is_composite == False)  # noqa: E712
        q = q.filter(database_manager.SourceItem.status == "linked")
        if limit and int(limit) > 0:
            q = q.limit(int(limit))

        buckets: dict[tuple[str, str, str], list[database_manager.SourceItem]] = defaultdict(list)
        for row in q.yield_per(2000):
            key = (_norm(row.derived_term or ""), _norm(row.derived_variation or ""), _norm(row.derived_physical_form or ""))
            buckets[key].append(row)

        for (term_n, var_n, form_n), rows in buckets.items():
            # canonical casing: prefer CosIng’s derived_term/variation/form when present
            def _pick_attr(attr: str) -> str:
                cos = [getattr(r, attr) for r in rows if (r.source or "").lower() == "cosing" and _clean(getattr(r, attr))]
                if cos:
                    return _clean(cos[0])
                anyv = [getattr(r, attr) for r in rows if _clean(getattr(r, attr))]
                return _clean(anyv[0]) if anyv else ""

            term = _pick_attr("derived_term")
            variation = _pick_attr("derived_variation")
            physical_form = _pick_attr("derived_physical_form")

            # aggregate parts
            parts = sorted({p for p in (_clean(getattr(r, "derived_part", "")) for r in rows) if p})

            # aggregate CAS numbers
            cas = sorted({c for c in (_clean(getattr(r, "cas_number", "")) for r in rows) if c})

            # aggregate sources
            source_counts = Counter([(r.source or "unknown").lower() for r in rows if (r.source or "").strip()])
            sources_json = json.dumps({"source_counts": dict(source_counts)}, ensure_ascii=False, sort_keys=True)

            # aggregate deterministic specs from source_items (union)
            merged_specs: dict[str, Any] = {}
            merged_spec_sources: dict[str, Any] = {}
            merged_notes: list[str] = []
            for r in rows:
                try:
                    s = json.loads(_clean(getattr(r, "derived_specs_json", "")) or "{}")
                    if isinstance(s, dict):
                        for k, v in s.items():
                            if k not in merged_specs:
                                merged_specs[k] = v
                            else:
                                # preserve conflicting values as a list
                                if merged_specs[k] == v:
                                    continue
                                cur = merged_specs[k]
                                if not isinstance(cur, list):
                                    cur = [cur]
                                if v not in cur:
                                    cur.append(v)
                                merged_specs[k] = cur
                except Exception:
                    pass
                try:
                    ss = json.loads(_clean(getattr(r, "derived_specs_sources_json", "")) or "{}")
                    if isinstance(ss, dict):
                        for k, v in ss.items():
                            merged_spec_sources.setdefault(k, v)
                except Exception:
                    pass
                try:
                    nn = json.loads(_clean(getattr(r, "derived_specs_notes_json", "")) or "[]")
                    if isinstance(nn, list):
                        for n in nn:
                            nt = _clean(n)
                            if nt and nt not in merged_notes:
                                merged_notes.append(nt)
                except Exception:
                    pass

            merged = database_manager.MergedItemForm(
                derived_term=term,
                derived_variation=variation,
                derived_physical_form=physical_form,
                derived_parts_json=json.dumps(parts, ensure_ascii=False, sort_keys=True),
                cas_numbers_json=json.dumps(cas, ensure_ascii=False, sort_keys=True),
                member_source_item_keys_json=json.dumps([r.key for r in rows], ensure_ascii=False, sort_keys=True),
                sources_json=sources_json,
                merged_specs_json=json.dumps(merged_specs, ensure_ascii=False, sort_keys=True),
                merged_specs_sources_json=json.dumps(merged_spec_sources, ensure_ascii=False, sort_keys=True),
                merged_specs_notes_json=json.dumps(sorted(set(merged_notes)), ensure_ascii=False, sort_keys=True),
                source_row_count=len(rows),
                has_cosing=bool(source_counts.get("cosing")),
                has_tgsc=bool(source_counts.get("tgsc")),
            )
            session.add(merged)
            session.flush()  # get merged.id
            created += 1

            for r in rows:
                if getattr(r, "merged_item_id", None) != merged.id:
                    r.merged_item_id = merged.id
                    updated_links += 1

    return {"merged_items": created, "source_items_linked": updated_links}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Merge ingested source_items into deduped item-forms")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    stats = merge_source_items(limit=int(args.limit or 0))
    LOGGER.info("merged source item forms: %s", stats)


if __name__ == "__main__":
    main()

