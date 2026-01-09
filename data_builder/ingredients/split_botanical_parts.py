"""Deterministic botanical part split (binomial botanicals only).

Goal:
- Some botanicals are condensed under the binomial base term (e.g., 'Vitis vinifera')
  while maker-facing usage treats Leaf/Seed/Fruit/etc. as distinct ingredient definitions.
- This post-pass splits ONLY when we have evidence of multiple plant parts within a binomial term.

Rules:
- Only split when the base term looks like a binomial and is Plant-Derived.
- Only split when >=2 distinct parts are observed across that term's merged item-forms.
- Re-home merged_item_forms under new part-level terms.
- Ensure every new part-level term has an identity/self item (variation/form empty).

This pass is deterministic, DB-only, and does not use any CSV artifacts.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from . import database_manager

LOGGER = logging.getLogger(__name__)


_BINOMIAL_RE = re.compile(r"^[A-Z][a-z]+ [a-z]{2,}\b")

# Canonical part tokens (title case).
_PARTS = [
    "Leaf",
    "Seed",
    "Fruit",
    "Berry",
    "Flower",
    "Root",
    "Bark",
    "Stem",
    "Vine",
    "Shoot",
    "Skin",
    "Sap",
    "Wood",
    "Bud",
    "Needle",
    "Cone",
    "Kernel",
    "Nut",
    "Herb",
    "Rhizome",
    "Peel",
    "Rind",
    "Branch",
    "Shell",
    "Seedcoat",
    "Sprout",
    "Gum",
    "Resin",
    "Wax",
    "Juice",
]

_PART_ALIASES = {
    "cera": "Wax",
    "resina": "Resin",
}


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _load_json_list(text: str) -> list[str]:
    try:
        data = json.loads(text or "[]")
        if isinstance(data, list):
            out: list[str] = []
            for x in data:
                t = _clean(x)
                if t:
                    out.append(t)
            return out
    except Exception:
        return []
    return []


def _infer_part_from_variation(variation: str) -> str:
    v = _clean(variation)
    if not v:
        return ""
    # Look for exact part tokens in variation (case-insensitive).
    low = v.lower()
    for p in _PARTS:
        if re.search(rf"\b{re.escape(p.lower())}\b", low):
            return p
    for alias, p in _PART_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", low):
            return p
    return ""


def _pick_primary_part(parts: list[str], variation: str) -> str:
    # Prefer explicit merged parts list, else infer from variation.
    normalized = []
    for p in parts:
        t = _clean(p)
        if not t:
            continue
        # normalize common aliases/casing
        low = t.lower()
        if low in _PART_ALIASES:
            normalized.append(_PART_ALIASES[low])
        else:
            normalized.append(t.title() if t.islower() else t)

    for p in _PARTS:
        if p in normalized:
            return p

    inferred = _infer_part_from_variation(variation)
    return inferred


def split_botanical_parts(*, limit_terms: int = 0) -> dict[str, int]:
    """Apply the botanical part split to merged_item_forms + normalized_terms."""
    database_manager.ensure_tables_exist()

    scanned_terms = 0
    updated_item_forms = 0
    created_terms = 0
    created_self_items = 0

    with database_manager.get_session() as session:
        # Load candidate base terms from normalized_terms (Plant-Derived + binomial-looking).
        q = session.query(database_manager.NormalizedTerm).order_by(database_manager.NormalizedTerm.term.asc())
        for nt in q.yield_per(500):
            if limit_terms and scanned_terms >= int(limit_terms):
                break
            term = _clean(nt.term)
            if not term or not _BINOMIAL_RE.match(term):
                continue
            if _clean(nt.origin) != "Plant-Derived":
                continue

            scanned_terms += 1

            # Pull merged item forms for this base term.
            rows = (
                session.query(database_manager.MergedItemForm)
                .filter(database_manager.MergedItemForm.derived_term == term)
                .order_by(database_manager.MergedItemForm.id.asc())
                .all()
            )
            if not rows:
                continue

            # Determine distinct parts present across the term.
            distinct_parts: set[str] = set()
            per_row_part: dict[int, str] = {}
            for r in rows:
                parts = _load_json_list(_clean(r.derived_parts_json))
                part = _pick_primary_part(parts, _clean(r.derived_variation))
                if part:
                    distinct_parts.add(part)
                    per_row_part[int(r.id)] = part

            # Only split when there is evidence of multiple parts within the same binomial term.
            if len(distinct_parts) < 2:
                continue

            # Create/ensure part-level terms and re-home item-forms.
            for r in rows:
                part = per_row_part.get(int(r.id), "")
                if not part:
                    continue  # keep base term for no-part forms

                new_term = f"{term} {part}".strip()
                if _clean(r.derived_term) != new_term:
                    r.derived_term = new_term
                    updated_item_forms += 1

                # Ensure normalized_terms row exists for the part term.
                existing = session.get(database_manager.NormalizedTerm, new_term)
                if existing is None:
                    # Copy base row and adjust minimal fields.
                    sources = {}
                    try:
                        sources = json.loads(_clean(nt.sources_json) or "{}")
                        if not isinstance(sources, dict):
                            sources = {}
                    except Exception:
                        sources = {}
                    sources = dict(sources)
                    sources.setdefault("botanical_part_split", []).append({"from": term, "part": part})

                    session.add(
                        database_manager.NormalizedTerm(
                            term=new_term,
                            seed_category=nt.seed_category,
                            botanical_name=nt.botanical_name,
                            inci_name=nt.inci_name,
                            cas_number=nt.cas_number,
                            description=nt.description,
                            ingredient_category=nt.ingredient_category,
                            origin=nt.origin,
                            refinement_level=nt.refinement_level,
                            derived_from="botanical_part_split",
                            overall_confidence=nt.overall_confidence,
                            sources_json=json.dumps(sources, ensure_ascii=False, sort_keys=True),
                        )
                    )
                    created_terms += 1

            # Ensure each part term gets a self/identity item form.
            for part in sorted(distinct_parts):
                part_term = f"{term} {part}".strip()
                exists = (
                    session.query(database_manager.MergedItemForm.id)
                    .filter(
                        database_manager.MergedItemForm.derived_term == part_term,
                        (database_manager.MergedItemForm.derived_variation == "") | (database_manager.MergedItemForm.derived_variation.is_(None)),
                        (database_manager.MergedItemForm.derived_physical_form == "") | (database_manager.MergedItemForm.derived_physical_form.is_(None)),
                    )
                    .first()
                )
                if exists:
                    continue

                session.add(
                    database_manager.MergedItemForm(
                        derived_term=part_term,
                        derived_variation="",
                        derived_physical_form="",
                        derived_parts_json=json.dumps([part], ensure_ascii=False, sort_keys=True),
                        cas_numbers_json="[]",
                        member_source_item_keys_json="[]",
                        sources_json=json.dumps({"synthetic_self_item": True, "from_term": term, "part": part}, ensure_ascii=False, sort_keys=True),
                        merged_specs_json="{}",
                        merged_specs_sources_json="{}",
                        merged_specs_notes_json="[]",
                        source_row_count=0,
                        has_cosing=False,
                        has_tgsc=False,
                    )
                )
                created_self_items += 1

    return {
        "terms_scanned": scanned_terms,
        "item_forms_rehomed": updated_item_forms,
        "new_terms_created": created_terms,
        "self_items_created": created_self_items,
    }

