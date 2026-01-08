"""PubChem item pipeline (pre-AI).

Stage 1 (items): match merged_item_forms -> PubChem CID.
Stage 2 (items): apply PubChem cached bundles into merged_item_forms.merged_specs_json (fill-only).

Notes:
- Uses PubChem PUG REST name->CID resolution for both CAS and names.
- Strict matching: accept only single-CID results; multi-CID -> ambiguous (no guessing).
- Resume-safe: uses pubchem_item_matches status.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Optional

import requests
import re

from . import database_manager

LOGGER = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

_RE_CAS = re.compile(r"\b(\d{2,7}-\d{2}-\d)\b")


def _clean(value: Any) -> str:
    return ("" if value is None else str(value)).strip()


def _json_list(text: str) -> list[Any]:
    try:
        val = json.loads(text or "[]")
        return val if isinstance(val, list) else []
    except Exception:
        return []


def _json_dict(text: str) -> dict[str, Any]:
    try:
        val = json.loads(text or "{}")
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def _merge_fill_only(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in patch.items():
        if k in out and out.get(k) not in (None, "", [], {}):
            continue
        out[k] = v
    return out


def _request_json(session: requests.Session, url: str, *, timeout: float = 20.0) -> dict[str, Any] | None:
    retries = int(os.getenv("PUBCHEM_RETRIES", "5"))
    backoff = float(os.getenv("PUBCHEM_BACKOFF_SECONDS", "0.6"))
    sleep_seconds = float(os.getenv("PUBCHEM_SLEEP_SECONDS", "0.02"))

    last_exc: Exception | None = None
    last_status: int | None = None
    for attempt in range(1, retries + 1):
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        try:
            resp = session.get(url, timeout=timeout)
            last_status = int(resp.status_code)
            if resp.status_code in (400, 404):
                return None
            if resp.status_code in (429, 503):
                time.sleep(backoff * attempt)
                continue
            resp.raise_for_status()
            blob = resp.json()
            return blob if isinstance(blob, dict) else None
        except Exception as exc:  # pylint: disable=broad-except
            last_exc = exc
            time.sleep(backoff * attempt)
            continue
    if last_exc:
        raise last_exc
    # If we exhausted retries due to throttling/server busy, treat as error (not no-match).
    if last_status in (429, 503):
        raise RuntimeError(f"pubchem_unavailable:{last_status}")
    return None


def _resolve_to_cids(name: str) -> list[int]:
    ident = _clean(name)
    if not ident:
        return []
    quoted = requests.utils.quote(ident)
    url = f"{PUBCHEM_BASE}/compound/name/{quoted}/cids/JSON"
    blob = _request_json(requests.Session(), url, timeout=20.0) or {}
    cids = (blob or {}).get("IdentifierList", {}).get("CID", [])
    if isinstance(cids, list):
        out: list[int] = []
        for c in cids:
            try:
                out.append(int(c))
            except Exception:
                continue
        return out
    return []


def _build_best_name(term: str, variation: str, physical_form: str) -> str:
    parts = [p for p in [_clean(term), _clean(variation), _clean(physical_form)] if p]
    # For PubChem name lookup, keep it simple; variations like "Seed Oil" can help.
    return " ".join(parts).strip()


def _match_one(merged_item_id: int) -> tuple[int, str, Optional[int], Optional[str], list[int], Optional[str]]:
    """Return (id, status, cid, matched_by, candidates, error)."""
    try:
        database_manager.ensure_tables_exist()
        # IMPORTANT: this is called in threads; keep DB sessions short and do not block.
        with database_manager.get_session() as session:
            mif = session.get(database_manager.MergedItemForm, int(merged_item_id))
            if mif is None:
                return merged_item_id, "error", None, None, [], "missing_merged_item_form"
            cas_list = _json_list(mif.cas_numbers_json or "[]")
            cas_candidates = [str(x).strip() for x in cas_list if isinstance(x, (str, int, float)) and str(x).strip()]
            term = _clean(getattr(mif, "derived_term", ""))
            variation = _clean(getattr(mif, "derived_variation", ""))
            form = _clean(getattr(mif, "derived_physical_form", ""))
            # Fast path: if the base term already has a PubChem CID, reuse it for this item-form.
            if term:
                tmatch = session.get(database_manager.PubChemTermMatch, term)
                if tmatch is not None and getattr(tmatch, "status", None) == "matched" and getattr(tmatch, "cid", None):
                    cid = int(tmatch.cid)
                    return merged_item_id, "matched", cid, "term_map", [cid], None

        allow_network = os.getenv("PUBCHEM_ITEM_ENABLE_NETWORK", "0").strip() in {"1", "true", "True"}
        if not allow_network:
            return merged_item_id, "no_match", None, None, [], None

        # CAS-first (highest precision) - network fallback.
        for cas in cas_candidates[:3]:
            cids = _resolve_to_cids(cas)
            if len(cids) == 1:
                return merged_item_id, "matched", int(cids[0]), "cas", cids, None
            if len(cids) > 1:
                return merged_item_id, "ambiguous", None, "cas", cids[:50], f"ambiguous_candidates:{len(cids)}"

        # Name fallback (term + variation/form).
        name = _build_best_name(term, variation, form)
        if name:
            cids2 = _resolve_to_cids(name)
            if len(cids2) == 1:
                return merged_item_id, "matched", int(cids2[0]), "name", cids2, None
            if len(cids2) > 1:
                return merged_item_id, "ambiguous", None, "name", cids2[:50], f"ambiguous_candidates:{len(cids2)}"

        # Term-only fallback.
        if term:
            cids3 = _resolve_to_cids(term)
            if len(cids3) == 1:
                return merged_item_id, "matched", int(cids3[0]), "term", cids3, None
            if len(cids3) > 1:
                return merged_item_id, "ambiguous", None, "term", cids3[:50], f"ambiguous_candidates:{len(cids3)}"

        return merged_item_id, "no_match", None, None, [], None
    except Exception as exc:  # pylint: disable=broad-except
        return merged_item_id, "error", None, None, [], str(exc)

def _build_cached_cas_map() -> dict[str, int]:
    """Build CAS->CID mapping from cached PubChem PUG View JSON (offline, best-effort).

    If a CAS appears under multiple CIDs, it is excluded (avoid false positives).
    """
    database_manager.ensure_tables_exist()
    cas_to_cids: dict[str, set[int]] = {}
    # 1) From cached PubChem PUG View JSON (CID-level cache)
    with database_manager.get_session() as session:
        q = session.query(database_manager.PubChemCompound.cid, database_manager.PubChemCompound.pug_view_json)
        for cid, blob in q.yield_per(200):
            if cid is None:
                continue
            text = blob or ""
            if not isinstance(text, str) or not text:
                continue
            for cas in set(_RE_CAS.findall(text)):
                cas_to_cids.setdefault(cas, set()).add(int(cid))

    # 2) From term-level CAS numbers where the term was matched to a CID.
    with database_manager.get_session() as session:
        q2 = (
            session.query(database_manager.NormalizedTerm.cas_number, database_manager.PubChemTermMatch.cid)
            .join(database_manager.PubChemTermMatch, database_manager.PubChemTermMatch.term == database_manager.NormalizedTerm.term)
            .filter(database_manager.PubChemTermMatch.status == "matched")
            .filter(database_manager.PubChemTermMatch.cid.isnot(None))
        )
        for cas, cid in q2.yield_per(500):
            c = _clean(cas)
            if not c:
                continue
            m = _RE_CAS.search(c)
            if not m:
                continue
            try:
                cas_to_cids.setdefault(m.group(1), set()).add(int(cid))
            except Exception:
                continue
    out: dict[str, int] = {}
    for cas, cids in cas_to_cids.items():
        if len(cids) == 1:
            out[cas] = next(iter(cids))
    return out


def _select_item_ids(limit: int | None) -> list[int]:
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        q = session.query(database_manager.MergedItemForm.id).outerjoin(
            database_manager.PubChemItemMatch,
            database_manager.PubChemItemMatch.merged_item_id == database_manager.MergedItemForm.id,
        )
        q = q.filter((database_manager.PubChemItemMatch.merged_item_id.is_(None)) | (database_manager.PubChemItemMatch.status.in_(["pending", "error"])))
        # Prioritize rows with CAS numbers (highest match likelihood/precision).
        # SQLite JSON isn't guaranteed; use simple string heuristics.
        q = q.order_by(
            database_manager.MergedItemForm.cas_numbers_json.in_(["[]", "", None]).asc(),
            database_manager.MergedItemForm.id.asc(),
        )
        if limit:
            q = q.limit(int(limit))
        return [int(r[0]) for r in q.all() if r and r[0] is not None]


def match_stage(*, limit: int | None, workers: int) -> dict[str, int]:
    ids = _select_item_ids(limit)
    stats = {"attempted": 0, "matched": 0, "no_match": 0, "ambiguous": 0, "error": 0}
    if not ids:
        return stats

    # Fast path: do a DB-only term_map match in a single session (no threads, avoids SQLite pool contention).
    allow_network = os.getenv("PUBCHEM_ITEM_ENABLE_NETWORK", "0").strip() in {"1", "true", "True"}
    if not allow_network:
        # Build CAS->CID map from cached PubChem data (offline).
        cas_map = _build_cached_cas_map()
        now = datetime.now(timezone.utc)
        database_manager.ensure_tables_exist()
        with database_manager.get_session() as session:
            for merged_item_id in ids:
                stats["attempted"] += 1
                mif = session.get(database_manager.MergedItemForm, int(merged_item_id))
                term = _clean(getattr(mif, "derived_term", "")) if mif is not None else ""
                cid: Optional[int] = None
                matched_by: Optional[str] = None
                if term:
                    tmatch = session.get(database_manager.PubChemTermMatch, term)
                    if tmatch is not None and getattr(tmatch, "status", None) == "matched" and getattr(tmatch, "cid", None):
                        cid = int(tmatch.cid)
                        matched_by = "term_map"
                # CAS fallback using cached PubChem map (higher precision than term_map).
                if not cid and mif is not None:
                    cas_list = _json_list(mif.cas_numbers_json or "[]")
                    for cas in [str(x).strip() for x in cas_list if str(x).strip()]:
                        cid2 = cas_map.get(cas)
                        if cid2:
                            cid = int(cid2)
                            matched_by = "cas_cache"
                            break

                status = "matched" if cid else "no_match"
                stats[status] = stats.get(status, 0) + 1
                row = session.get(database_manager.PubChemItemMatch, int(merged_item_id))
                if row is None:
                    row = database_manager.PubChemItemMatch(merged_item_id=int(merged_item_id), status="pending")
                    session.add(row)
                row.status = status
                row.cid = cid
                row.matched_by = matched_by
                row.candidates_json = json.dumps([cid] if cid else [], ensure_ascii=False)
                row.error = None
                row.updated_at = now
        return stats

    # Network-enabled path (threaded).
    now = datetime.now(timezone.utc)
    results: list[tuple[int, str, Optional[int], Optional[str], list[int], Optional[str]]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futs = [pool.submit(_match_one, int(i)) for i in ids]
        for fut in as_completed(futs):
            results.append(fut.result())

    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        for merged_item_id, status, cid, matched_by, candidates, error in results:
            stats["attempted"] += 1
            stats[status] = stats.get(status, 0) + 1
            row = session.get(database_manager.PubChemItemMatch, int(merged_item_id))
            if row is None:
                row = database_manager.PubChemItemMatch(merged_item_id=int(merged_item_id), status="pending")
                session.add(row)
            row.status = status
            row.cid = cid
            row.matched_by = matched_by
            row.candidates_json = json.dumps(candidates, ensure_ascii=False)
            row.error = error
            row.updated_at = now

    return stats


def apply_stage(*, limit: int | None) -> dict[str, int]:
    """Fill-only apply PubChem cached property bundle into merged_item_forms.merged_specs_json."""
    database_manager.ensure_tables_exist()
    updated = 0
    scanned = 0

    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.PubChemItemMatch)
            .filter(database_manager.PubChemItemMatch.status == "matched")
            .filter(database_manager.PubChemItemMatch.cid.isnot(None))
        )
        if limit:
            q = q.limit(int(limit))
        for match in q.yield_per(200):
            scanned += 1
            cid = int(match.cid) if match.cid is not None else 0
            if not cid:
                continue
            mif = session.get(database_manager.MergedItemForm, int(match.merged_item_id))
            if mif is None:
                continue
            comp = session.get(database_manager.PubChemCompound, int(cid))
            if comp is None:
                continue
            prop = _json_dict(comp.property_json or "{}")
            # Map PubChem keys into deterministic spec keys.
            patch = {
                "pubchem_cid": cid,
                "molecular_formula": prop.get("MolecularFormula"),
                "molecular_weight": prop.get("MolecularWeight"),
                "exact_mass": prop.get("ExactMass"),
                "inchi_key": prop.get("InChIKey"),
                "canonical_smiles": prop.get("CanonicalSMILES"),
                "iupac_name": prop.get("IUPACName"),
                "xlogp": prop.get("XLogP"),
                "tpsa": prop.get("TPSA"),
                "hbond_donor_count": prop.get("HBondDonorCount"),
                "hbond_acceptor_count": prop.get("HBondAcceptorCount"),
                "rotatable_bond_count": prop.get("RotatableBondCount"),
                "complexity": prop.get("Complexity"),
            }
            base_specs = _json_dict(mif.merged_specs_json or "{}")
            merged = _merge_fill_only(base_specs, {k: v for k, v in patch.items() if v not in (None, "")})
            if merged != base_specs:
                mif.merged_specs_json = json.dumps(merged, ensure_ascii=False, sort_keys=True)
                # Record provenance in merged_specs_sources_json.
                src = _json_dict(mif.merged_specs_sources_json or "{}")
                src = _merge_fill_only(src, {"pubchem": {"cid": cid, "matched_by": match.matched_by}})
                mif.merged_specs_sources_json = json.dumps(src, ensure_ascii=False, sort_keys=True)
                updated += 1

    return {"scanned": scanned, "updated": updated}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PubChem item pipeline (match + apply)")
    p.add_argument("--mode", choices=["match", "apply", "full"], default=os.getenv("PUBCHEM_ITEM_MODE", "full"))
    p.add_argument("--limit", type=int, default=int(os.getenv("PUBCHEM_ITEM_LIMIT", "500")))
    p.add_argument("--workers", type=int, default=int(os.getenv("PUBCHEM_WORKERS", "16")))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    limit = int(args.limit) if int(args.limit or 0) > 0 else None
    mode = str(args.mode)
    if mode in ("match", "full"):
        stats = match_stage(limit=limit, workers=int(args.workers or 1))
        LOGGER.info("pubchem item match stats: %s", stats)
    if mode in ("apply", "full"):
        stats2 = apply_stage(limit=limit)
        LOGGER.info("pubchem item apply stats: %s", stats2)


if __name__ == "__main__":
    main()

