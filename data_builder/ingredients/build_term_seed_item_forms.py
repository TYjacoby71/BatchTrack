"""Build `term_seed_item_forms` from `merged_item_forms` (pre-AI).

This produces a stable seed item list per term that downstream steps can enrich:
- PubChem enrichment (fill-only, before AI)
- Compiler completion (fill missing schema fields; do not invent identity)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from . import database_manager


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _json_loads(text: str, default: Any) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return default


def build_term_seed_item_forms() -> dict[str, int]:
    database_manager.ensure_tables_exist()
    created = 0
    updated = 0
    ensured_identity_items = 0

    with database_manager.get_session() as session:
        # Deterministic rebuild: clear existing seeds
        session.query(database_manager.TermSeedItemForm).delete()

        # Build seed rows from merged item forms
        by_term: dict[str, list[database_manager.TermSeedItemForm]] = {}
        for m in session.query(database_manager.MergedItemForm).yield_per(2000):
            term = _clean(getattr(m, "derived_term", ""))
            if not term:
                continue
            var = _clean(getattr(m, "derived_variation", "")) or ""
            form = _clean(getattr(m, "derived_physical_form", "")) or ""
            variation_bypass = (var == "")
            form_bypass = (form == "")
            cas_numbers_json = _clean(getattr(m, "cas_numbers_json", "")) or "[]"
            specs_json = _clean(getattr(m, "merged_specs_json", "")) or "{}"

            # sources_json keeps provenance and also carries derived_parts for later botanical splitting
            src = _json_loads(_clean(getattr(m, "merged_specs_sources_json", "")) or "{}", {})
            if not isinstance(src, dict):
                src = {}
            parts = _json_loads(_clean(getattr(m, "derived_parts_json", "")) or "[]", [])
            if isinstance(parts, list) and parts:
                src.setdefault("derived_parts", parts)

            seed = database_manager.TermSeedItemForm(
                term=term,
                variation=var,
                physical_form=form,
                variation_bypass=bool(variation_bypass),
                form_bypass=bool(form_bypass),
                cas_numbers_json=cas_numbers_json,
                specs_json=specs_json,
                sources_json=json.dumps(src, ensure_ascii=False, sort_keys=True),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            session.add(seed)
            created += 1
            by_term.setdefault(term, []).append(seed)

        # Add a self/identity item only in the "multi-item cluster missing a base item" case.
        # This keeps the seed universe close to the deduped item-forms while still ensuring
        # a stable baseline item for multi-form ingredients (maker-facing).
        for term, seeds in by_term.items():
            if len(seeds) <= 1:
                continue
            has_identity = any((_clean(s.variation) == "") for s in seeds)
            if has_identity:
                continue
            session.add(
                database_manager.TermSeedItemForm(
                    term=term,
                    variation="",
                    physical_form="",
                    variation_bypass=True,
                    form_bypass=True,
                    cas_numbers_json="[]",
                    specs_json="{}",
                    sources_json=json.dumps({"seed": "identity_item", "reason": "multi_item_missing_base"}, ensure_ascii=False, sort_keys=True),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            ensured_identity_items += 1

    return {"seed_rows_created": created, "identity_items_added": ensured_identity_items, "updated": updated}

