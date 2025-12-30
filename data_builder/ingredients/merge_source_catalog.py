"""Build a merged source catalog from CosIng + TGSC.

This creates/updates `source_catalog_items` in compiler_state.db.

Merge strategy (deterministic):
1) Ingest CosIng first (authoritative for INCI + CAS + EC + Functions/Restrictions).
2) Overlay TGSC by matching:
   - CAS match (highest confidence)
   - EC/EINECS match (next)
   - INCI exact match (rare; only when TGSC 'common_name' equals an INCI string, usually not desired)
3) Fill missing fields only (do not overwrite CosIng identifiers).

Guardrail:
- Never put INCI into common_name. common_name is TGSC-only (or left null).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import database_manager

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_SOURCES_DIR = BASE_DIR / "data_sources"


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().strip('"').strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _first_cas(value: str) -> str:
    v = _clean_text(value)
    if not v or v in {"-", "—"}:
        return ""
    return v.split(",")[0].strip()


def _clean_ec(value: str) -> str:
    v = _clean_text(value)
    if not v or v in {"-", "—"}:
        return ""
    return v


def _norm_inci(value: str) -> str:
    v = _clean_text(value)
    v = v.upper()
    v = re.sub(r"\s+", " ", v).strip()
    return v


def _parse_cosing_functions(value: str) -> list[str]:
    raw = _clean_text(value)
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    return sorted({p for p in parts if p})


def _merge_union_text(existing: str | None, incoming: str | None) -> str | None:
    """Merge two free-text synonym blobs conservatively."""
    a = _clean_text(existing)
    b = _clean_text(incoming)
    if not a and not b:
        return None
    if not a:
        return b
    if not b:
        return a
    if b.lower() in a.lower():
        return a
    if a.lower() in b.lower():
        return b
    return a + "; " + b


def build_catalog(
    *,
    cosing_path: Path,
    tgsc_path: Path,
    limit: Optional[int] = None,
    include: Optional[list[str]] = None,
) -> dict[str, int]:
    """Build/merge the source catalog.

    Returns counts: {"cosing_rows": x, "tgsc_rows": y, "catalog_upserts": z}
    """
    include_tokens = [t.strip().lower() for t in (include or []) if (t or "").strip()]
    database_manager.ensure_tables_exist()

    def _include_ok(text: str) -> bool:
        if not include_tokens:
            return True
        tl = (text or "").lower()
        return any(tok in tl for tok in include_tokens)

    # Build fast lookup maps for existing catalog rows (by CAS / EC / INCI)
    cas_to_key: dict[str, str] = {}
    ec_to_key: dict[str, str] = {}
    inci_to_key: dict[str, str] = {}

    upserts = 0
    cosing_count = 0
    tgsc_count = 0

    with database_manager.get_session() as session:
        existing = session.query(database_manager.SourceCatalogItem).all()
        for row in existing:
            if row.cas_number:
                cas_to_key[row.cas_number.strip()] = row.key
            if row.ec_number:
                ec_to_key[row.ec_number.strip()] = row.key
            if row.inci_name:
                inci_to_key[_norm_inci(row.inci_name)] = row.key

        # ----------------------------
        # Pass 1: CosIng
        # ----------------------------
        with cosing_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for idx, row in enumerate(reader):
                if limit and (cosing_count + tgsc_count) >= int(limit):
                    break
                inci = _clean_text(row.get("INCI name") or row.get("INCI Name") or "")
                if not inci:
                    continue
                if not _include_ok(inci):
                    continue

                cosing_ref = _clean_text(row.get("COSING Ref No") or "")
                cas = _first_cas(row.get("CAS No") or "")
                ec = _clean_ec(row.get("EC No") or "")
                key = ""
                if cas:
                    key = f"cas:{cas}"
                elif ec:
                    key = f"ec:{ec}"
                else:
                    key = f"inci:{_norm_inci(inci)}"

                item = session.get(database_manager.SourceCatalogItem, key)
                if item is None:
                    item = database_manager.SourceCatalogItem(key=key)
                    session.add(item)
                    upserts += 1

                # Identifiers (authoritative)
                item.inci_name = item.inci_name or inci
                item.cas_number = item.cas_number or (cas or None)
                item.ec_number = item.ec_number or (ec or None)

                # CosIng fields
                if cosing_ref:
                    try:
                        refs = json.loads(item.cosing_ref_nos_json or "[]")
                        if not isinstance(refs, list):
                            refs = []
                    except Exception:
                        refs = []
                    if cosing_ref not in refs:
                        refs.append(cosing_ref)
                    item.cosing_ref_nos_json = json.dumps(sorted(set(refs)), ensure_ascii=False)

                item.cosing_inn_name = item.cosing_inn_name or _clean_text(row.get("INN name") or "") or None
                item.cosing_ph_eur_name = item.cosing_ph_eur_name or _clean_text(row.get("Ph. Eur. Name") or "") or None
                item.cosing_description = item.cosing_description or _clean_text(row.get("Chem/IUPAC Name / Description") or "") or None
                item.cosing_restriction = item.cosing_restriction or _clean_text(row.get("Restriction") or "") or None
                item.cosing_functions_raw = item.cosing_functions_raw or _clean_text(row.get("Function") or "") or None
                # Also maintain parsed function list
                funcs = _parse_cosing_functions(row.get("Function") or "")
                if funcs:
                    item.cosing_functions_json = json.dumps(funcs, ensure_ascii=False)
                item.cosing_update_date = item.cosing_update_date or _clean_text(row.get("Update Date") or "") or None

                # Provenance
                try:
                    src = json.loads(item.sources_json or "{}")
                    if not isinstance(src, dict):
                        src = {}
                except Exception:
                    src = {}
                src.setdefault("cosing", {}).setdefault("ref_nos", [])
                if cosing_ref and cosing_ref not in src["cosing"]["ref_nos"]:
                    src["cosing"]["ref_nos"].append(cosing_ref)
                item.sources_json = json.dumps(src, ensure_ascii=False, sort_keys=True)
                item.merged_at = datetime.now(timezone.utc)

                # Update lookup maps
                if item.cas_number:
                    cas_to_key[item.cas_number.strip()] = item.key
                if item.ec_number:
                    ec_to_key[item.ec_number.strip()] = item.key
                if item.inci_name:
                    inci_to_key[_norm_inci(item.inci_name)] = item.key

                cosing_count += 1

        # ----------------------------
        # Pass 2: TGSC overlay
        # ----------------------------
        with tgsc_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if limit and (cosing_count + tgsc_count) >= int(limit):
                    break
                name = _clean_text(row.get("common_name") or row.get("name") or "")
                if not name:
                    continue
                if not _include_ok(name):
                    continue

                cas = _first_cas(row.get("cas_number") or "")
                einecs = _clean_text(row.get("einecs_number") or "")

                key = ""
                # Match priority: CAS -> EC/EINECS -> exact INCI string (rare, last resort)
                if cas and cas in cas_to_key:
                    key = cas_to_key[cas]
                elif einecs and einecs in ec_to_key:
                    key = ec_to_key[einecs]
                else:
                    # Create new record for TGSC-only rows
                    key = f"cas:{cas}" if cas else (f"ec:{einecs}" if einecs else f"tgsc:{name.lower()}")

                item = session.get(database_manager.SourceCatalogItem, key)
                if item is None:
                    item = database_manager.SourceCatalogItem(key=key)
                    session.add(item)
                    upserts += 1

                # Never populate common_name from INCI; only from TGSC.
                if name and not item.common_name:
                    # TGSC common_name sometimes has trailing comma
                    item.common_name = name.rstrip(",").strip() or None

                # Fill identifiers if missing
                item.cas_number = item.cas_number or (cas or None)
                item.ec_number = item.ec_number or (einecs or None)

                # TGSC fields (fill only if empty)
                item.tgsc_category = item.tgsc_category or _clean_text(row.get("category") or "") or None
                item.tgsc_botanical_name = item.tgsc_botanical_name or _clean_text(row.get("botanical_name") or "") or None
                item.tgsc_einecs_number = item.tgsc_einecs_number or (einecs or None)
                item.tgsc_fema_number = item.tgsc_fema_number or _clean_text(row.get("fema_number") or "") or None
                item.tgsc_molecular_formula = item.tgsc_molecular_formula or _clean_text(row.get("molecular_formula") or "") or None
                item.tgsc_molecular_weight = item.tgsc_molecular_weight or _clean_text(row.get("molecular_weight") or "") or None
                item.tgsc_boiling_point = item.tgsc_boiling_point or _clean_text(row.get("boiling_point") or "") or None
                item.tgsc_melting_point = item.tgsc_melting_point or _clean_text(row.get("melting_point") or "") or None
                item.tgsc_density = item.tgsc_density or _clean_text(row.get("density") or "") or None
                item.tgsc_odor_description = item.tgsc_odor_description or _clean_text(row.get("odor_description") or "") or None
                item.tgsc_flavor_description = item.tgsc_flavor_description or _clean_text(row.get("flavor_description") or "") or None
                item.tgsc_description = item.tgsc_description or _clean_text(row.get("description") or "") or None
                item.tgsc_uses = item.tgsc_uses or _clean_text(row.get("uses") or "") or None
                item.tgsc_safety_notes = item.tgsc_safety_notes or _clean_text(row.get("safety_notes") or "") or None
                item.tgsc_solubility = item.tgsc_solubility or _clean_text(row.get("solubility") or "") or None
                item.tgsc_synonyms = _merge_union_text(item.tgsc_synonyms, row.get("synonyms"))
                item.tgsc_natural_occurrence = item.tgsc_natural_occurrence or _clean_text(row.get("natural_occurrence") or "") or None
                item.tgsc_url = item.tgsc_url or _clean_text(row.get("url") or "") or None

                # Provenance
                try:
                    src = json.loads(item.sources_json or "{}")
                    if not isinstance(src, dict):
                        src = {}
                except Exception:
                    src = {}
                src.setdefault("tgsc", {}).setdefault("rows", 0)
                src["tgsc"]["rows"] = int(src["tgsc"]["rows"]) + 1
                item.sources_json = json.dumps(src, ensure_ascii=False, sort_keys=True)
                item.merged_at = datetime.now(timezone.utc)

                # Update lookup maps
                if item.cas_number:
                    cas_to_key[item.cas_number.strip()] = item.key
                if item.ec_number:
                    ec_to_key[item.ec_number.strip()] = item.key
                if item.inci_name:
                    inci_to_key[_norm_inci(item.inci_name)] = item.key

                tgsc_count += 1

    return {"cosing_rows": cosing_count, "tgsc_rows": tgsc_count, "catalog_upserts": upserts}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge CosIng + TGSC into source_catalog_items")
    parser.add_argument("--cosing", default=str(DATA_SOURCES_DIR / "cosing.csv"))
    parser.add_argument("--tgsc", default=str(DATA_SOURCES_DIR / "tgsc_ingredients.csv"))
    parser.add_argument("--limit", type=int, default=0, help="Optional cap (total rows processed across both sources)")
    parser.add_argument("--include", action="append", default=[], help="Only process rows whose name contains this substring (repeatable)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    limit = int(args.limit) if args.limit else None
    stats = build_catalog(
        cosing_path=Path(args.cosing).resolve(),
        tgsc_path=Path(args.tgsc).resolve(),
        limit=limit,
        include=list(args.include or []),
    )
    LOGGER.info("catalog merge done: %s", stats)


if __name__ == "__main__":
    main()

