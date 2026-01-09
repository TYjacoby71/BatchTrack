"""Deterministic enrichment of item-level specifications from source datasets.

Goal:
- Pull *all available* non-AI spec-like data from TGSC (and merged catalog) into source_items.
- Attach explicit provenance and notes so the UI can explain where values came from or why
  some values are left null (not applicable vs unknown).

This module does NOT touch the AI compiler or compiled tables (`ingredients`, `ingredient_items`).

Writes (per SourceItem row):
- source_items.derived_specs_json: JSON dict of extracted specs (strings/numbers as available)
- source_items.derived_specs_sources_json: JSON dict mapping spec field -> provenance string
- source_items.derived_specs_notes_json: JSON list of human-readable notes (defaults/not-applicable)
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


def _parse_first_float(text_value: str | None) -> float | None:
    """Extract the first float-like token from a TGSC-ish string."""
    if not isinstance(text_value, str):
        return None
    t = text_value.strip()
    if not t:
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)", t)
    if not m:
        return None
    try:
        return float(m.group(1))
    except Exception:
        return None


def _json_loads_safe(text: str, default: Any) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return default


def _merge_sources(dst: dict[str, str], src: dict[str, str]) -> dict[str, str]:
    out = dict(dst)
    for k, v in (src or {}).items():
        kk = _clean(k)
        vv = _clean(v)
        if not kk or not vv:
            continue
        out.setdefault(kk, vv)
    return out


def _add_note(notes: list[str], text: str) -> None:
    t = _clean(text)
    if not t:
        return
    if t not in notes:
        notes.append(t)


def _extract_tgsc_fields_from_payload(payload_json: str) -> dict[str, str]:
    """Pull TGSC CSV fields from a TGSC source_item payload_json if present."""
    payload = _json_loads_safe(payload_json or "{}", {})
    if not isinstance(payload, dict):
        return {}
    out: dict[str, str] = {}
    for k in (
        "molecular_formula",
        "molecular_weight",
        "boiling_point",
        "melting_point",
        "density",
        "solubility",
        "safety_notes",
        "odor_description",
        "flavor_description",
    ):
        v = _clean(payload.get(k))
        if v:
            out[k] = v
    return out


def derive_specs(*, limit: int = 0) -> dict[str, int]:
    database_manager.ensure_tables_exist()
    scanned = 0
    updated = 0

    with database_manager.get_session() as session:
        q = session.query(database_manager.SourceItem)
        if limit and int(limit) > 0:
            q = q.limit(int(limit))

        for row in q.yield_per(1000):
            scanned += 1

            # Only enrich “normal” items; keep composites as-is (still traceable via payload_json).
            if bool(getattr(row, "is_composite", False)):
                continue

            cas = _clean(getattr(row, "cas_number", None))
            source = _clean(getattr(row, "source", None)).lower()
            payload_json = _clean(getattr(row, "payload_json", None))

            specs: dict[str, Any] = {}
            sources: dict[str, str] = {}
            notes: list[str] = []

            # 1) Pull TGSC physchem via merged catalog (preferred because it's cross-source).
            if cas:
                cat = session.get(database_manager.SourceCatalogItem, f"cas:{cas}")
                if cat is not None:
                    if _clean(getattr(cat, "tgsc_density", None)):
                        specs["density"] = _clean(getattr(cat, "tgsc_density", None))
                        sources["density"] = f"tgsc_catalog(cas:{cas})"
                    if _clean(getattr(cat, "tgsc_melting_point", None)):
                        specs["melting_point_text"] = _clean(getattr(cat, "tgsc_melting_point", None))
                        sources["melting_point_text"] = f"tgsc_catalog(cas:{cas})"
                        mp = _parse_first_float(_clean(getattr(cat, "tgsc_melting_point", None)))
                        if mp is not None:
                            specs["melting_point_c"] = mp
                            sources["melting_point_c"] = f"tgsc_catalog(cas:{cas})"
                    if _clean(getattr(cat, "tgsc_boiling_point", None)):
                        specs["boiling_point_text"] = _clean(getattr(cat, "tgsc_boiling_point", None))
                        sources["boiling_point_text"] = f"tgsc_catalog(cas:{cas})"
                        bp = _parse_first_float(_clean(getattr(cat, "tgsc_boiling_point", None)))
                        if bp is not None:
                            specs["boiling_point_c"] = bp
                            sources["boiling_point_c"] = f"tgsc_catalog(cas:{cas})"
                    if _clean(getattr(cat, "tgsc_molecular_weight", None)):
                        specs["molecular_weight_text"] = _clean(getattr(cat, "tgsc_molecular_weight", None))
                        sources["molecular_weight_text"] = f"tgsc_catalog(cas:{cas})"
                        mw = _parse_first_float(_clean(getattr(cat, "tgsc_molecular_weight", None)))
                        if mw is not None:
                            specs["molecular_weight"] = mw
                            sources["molecular_weight"] = f"tgsc_catalog(cas:{cas})"
                    if _clean(getattr(cat, "tgsc_molecular_formula", None)):
                        specs["molecular_formula"] = _clean(getattr(cat, "tgsc_molecular_formula", None))
                        sources["molecular_formula"] = f"tgsc_catalog(cas:{cas})"
                    if _clean(getattr(cat, "tgsc_solubility", None)):
                        specs["solubility"] = _clean(getattr(cat, "tgsc_solubility", None))
                        sources["solubility"] = f"tgsc_catalog(cas:{cas})"
                    if _clean(getattr(cat, "tgsc_safety_notes", None)):
                        specs["safety_notes"] = _clean(getattr(cat, "tgsc_safety_notes", None))
                        sources["safety_notes"] = f"tgsc_catalog(cas:{cas})"

            # 2) If this is a TGSC source row, also pull any fields directly from the payload_json.
            # This can capture fields even when the catalog keying didn't match for some reason.
            if source == "tgsc" and payload_json:
                tg = _extract_tgsc_fields_from_payload(payload_json)
                # Only fill missing keys; catalog wins when present.
                for k, v in tg.items():
                    if k in specs:
                        continue
                    specs[k] = v
                    sources[k] = "tgsc_payload"

            # 3) Deterministic “not applicable / left null” notes (no numeric guessing).
            form = _clean(getattr(row, "derived_physical_form", None))
            origin = _clean(getattr(row, "origin", None))
            category = _clean(getattr(row, "ingredient_category", None))

            # Hard-and-fast guidance for common craft specs:
            # - SAP and iodine are *fat/oil* metrics; for non-fats they are not applicable.
            if form and form not in {"Oil", "Butter", "Wax"}:
                _add_note(notes, "SAP (saponification) and iodine are fat/oil metrics; not applicable for this item form unless specifically sourced.")
            # - pH is typically meaningful for aqueous solutions; for solids/minerals it’s formulation-dependent.
            if origin in {"Mineral/Earth"} or (category.startswith("Mineral") if category else False):
                _add_note(notes, "pH is formulation-dependent for many minerals/solids; left null unless specifically sourced.")

            # Persist JSON blobs (stable shape).
            old_specs = _json_loads_safe(_clean(getattr(row, "derived_specs_json", "")) or "{}", {})
            old_sources = _json_loads_safe(_clean(getattr(row, "derived_specs_sources_json", "")) or "{}", {})
            old_notes = _json_loads_safe(_clean(getattr(row, "derived_specs_notes_json", "")) or "[]", [])
            if not isinstance(old_specs, dict):
                old_specs = {}
            if not isinstance(old_sources, dict):
                old_sources = {}
            if not isinstance(old_notes, list):
                old_notes = []

            new_specs = dict(old_specs)
            for k, v in specs.items():
                # keep existing if already present (ingestion should be stable)
                if k in new_specs and _clean(new_specs.get(k)) != "":
                    continue
                new_specs[k] = v
            new_sources = _merge_sources(old_sources, sources)
            new_notes = list(old_notes)
            for n in notes:
                _add_note(new_notes, n)

            new_specs_json = json.dumps(new_specs, ensure_ascii=False, sort_keys=True)
            new_sources_json = json.dumps(new_sources, ensure_ascii=False, sort_keys=True)
            new_notes_json = json.dumps(sorted(set([_clean(n) for n in new_notes if _clean(n)])), ensure_ascii=False)

            if (
                _clean(getattr(row, "derived_specs_json", "")) != new_specs_json
                or _clean(getattr(row, "derived_specs_sources_json", "")) != new_sources_json
                or _clean(getattr(row, "derived_specs_notes_json", "")) != new_notes_json
            ):
                row.derived_specs_json = new_specs_json
                row.derived_specs_sources_json = new_sources_json
                row.derived_specs_notes_json = new_notes_json
                updated += 1

    return {"scanned": scanned, "updated": updated}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Derive deterministic item specs into source_items")
    p.add_argument("--limit", type=int, default=0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    stats = derive_specs(limit=int(args.limit or 0))
    LOGGER.info("derived source item specs: %s", stats)


if __name__ == "__main__":
    main()

