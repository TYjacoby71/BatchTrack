"""Deterministic botanical part split (maker-facing).

Purpose:
- Some binomial-based botanicals are "condensed" at the species level (e.g., Vitis vinifera)
  while variations encode plant parts (Seed Oil, Leaf Extract, Fruit Powder, etc.).
- Makers often treat parts as distinct ingredients (Grape Seed Oil vs Grape Leaf Extract).

This post-pass:
- Only targets binomial terms (Genus species) where part signals exist.
- Promotes part-level terms (e.g., "Vitis vinifera Seed") and re-homes matching seed items.
- Strips the part prefix from the variation when it becomes redundant.
- Ensures each promoted term has an identity/self item (variation="", bypass flags true).
"""

from __future__ import annotations

import json
import re
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


_BINOMIAL_RE = re.compile(r"^[A-Z][a-z]+ [a-z]{2,}$")

_PARTS = {
    "Leaf",
    "Seed",
    "Fruit",
    "Flower",
    "Root",
    "Stem",
    "Bark",
    "Bud",
    "Peel",
    "Rind",
    "Kernel",
    "Nut",
    "Wood",
    "Cone",
    "Needle",
    "Rhizome",
}


def _infer_part_from_seed(seed: database_manager.TermSeedItemForm) -> str:
    # 1) Use derived_parts carried from merged_item_forms
    src = _json_loads(_clean(seed.sources_json) or "{}", {})
    parts = src.get("derived_parts") if isinstance(src, dict) else None
    if isinstance(parts, list) and parts:
        # if multiple, pick the first deterministically
        p = _clean(parts[0])
        return p if p in _PARTS else ""

    # 2) Parse from variation prefix: "Leaf Extract" -> Leaf
    var = _clean(seed.variation)
    if not var:
        return ""
    first = var.split(" ", 1)[0].strip()
    return first if first in _PARTS else ""


def _strip_part_prefix(variation: str, part: str) -> str:
    v = _clean(variation)
    p = _clean(part)
    if not v or not p:
        return v
    if v == p:
        return ""
    if v.startswith(p + " "):
        return v[len(p) + 1 :].strip()
    return v


def split_botanical_parts() -> dict[str, int]:
    database_manager.ensure_tables_exist()

    promoted_terms = 0
    moved_seeds = 0
    identity_added = 0

    with database_manager.get_session() as session:
        # Map normalized term -> row for metadata copying
        norm_rows = {r.term: r for r in session.query(database_manager.NormalizedTerm).all()}

        # Group seed items by term
        seeds_by_term: dict[str, list[database_manager.TermSeedItemForm]] = {}
        for s in session.query(database_manager.TermSeedItemForm).yield_per(5000):
            seeds_by_term.setdefault(s.term, []).append(s)

        for term, seeds in seeds_by_term.items():
            if not _BINOMIAL_RE.match(term):
                continue
            base_norm = norm_rows.get(term)
            # Scope: binomial-driven botanicals. Origin inference can be wrong for biotech rows
            # (e.g., callus culture / conditioned media) so we *do not* gate on origin here.

            # Identify part signals present
            parts_present: set[str] = set()
            for s in seeds:
                part = _infer_part_from_seed(s)
                if part:
                    parts_present.add(part)
            if not parts_present:
                continue

            # Promote each part-term and move matching seeds
            for part in sorted(parts_present):
                new_term = f"{term} {part}"
                if new_term not in norm_rows:
                    # Create normalized term row for promoted term (copy metadata)
                    if base_norm is not None:
                        row = database_manager.NormalizedTerm(
                            term=new_term,
                            seed_category=base_norm.seed_category,
                            botanical_name=base_norm.botanical_name,
                            inci_name=base_norm.inci_name,
                            cas_number=base_norm.cas_number,
                            common_name=None,
                            common_name_source=None,
                            description=base_norm.description,
                            ingredient_category=base_norm.ingredient_category,
                            origin=base_norm.origin,
                            refinement_level=base_norm.refinement_level,
                            derived_from=term,
                            ingredient_category_confidence=base_norm.ingredient_category_confidence,
                            origin_confidence=base_norm.origin_confidence,
                            refinement_confidence=base_norm.refinement_confidence,
                            derived_from_confidence=60,
                            overall_confidence=base_norm.overall_confidence,
                            sources_json=base_norm.sources_json,
                            normalized_at=datetime.utcnow(),
                        )
                    else:
                        row = database_manager.NormalizedTerm(term=new_term, origin="Plant-Derived", derived_from=term)
                    session.add(row)
                    norm_rows[new_term] = row
                    promoted_terms += 1

                # Move relevant seeds (those whose inferred part equals this part)
                for s in seeds:
                    if _infer_part_from_seed(s) != part:
                        continue
                    if s.term != new_term:
                        s.term = new_term
                        moved_seeds += 1
                    # Strip part prefix from variation now that part is in the term
                    stripped = _strip_part_prefix(_clean(s.variation), part)
                    if stripped != _clean(s.variation):
                        s.variation = stripped
                        s.variation_bypass = (stripped == "")
                    s.updated_at = datetime.utcnow()

                # Ensure identity/self item exists for the promoted term
                exists = (
                    session.query(database_manager.TermSeedItemForm.id)
                    .filter(database_manager.TermSeedItemForm.term == new_term)
                    .filter(database_manager.TermSeedItemForm.variation == "")
                    .filter(database_manager.TermSeedItemForm.physical_form == "")
                    .first()
                    is not None
                )
                if not exists:
                    session.add(
                        database_manager.TermSeedItemForm(
                            term=new_term,
                            variation="",
                            physical_form="",
                            variation_bypass=True,
                            form_bypass=True,
                            cas_numbers_json="[]",
                            specs_json="{}",
                            sources_json=json.dumps({"seed": "identity_item", "promoted_from": term}, ensure_ascii=False, sort_keys=True),
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                    )
                    identity_added += 1

    return {
        "promoted_terms": promoted_terms,
        "seed_items_moved": moved_seeds,
        "identity_items_added": identity_added,
    }

