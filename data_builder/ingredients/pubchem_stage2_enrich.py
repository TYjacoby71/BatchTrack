"""PubChem Stage 2: fetch & cache enrichment bundles for matched CIDs.

This is a deterministic pre-AI step that runs after Stage 1 has assigned CIDs.

It:
- reads `pubchem_term_matches` where status='matched'
- caches PubChem results per CID in `pubchem_compounds`
- (optionally) applies a fill-only merge into `normalized_terms.sources_json`

PubChem endpoints:
- PropertyTable (batchable): /compound/cid/<cids>/property/<props>/JSON
- PUG View (per-CID, slower): /pug_view/data/compound/<cid>/JSON
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import requests

from . import database_manager

LOGGER = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


def _clean_json(text: str) -> dict[str, Any]:
    try:
        blob = json.loads(text or "{}")
        return blob if isinstance(blob, dict) else {}
    except Exception:
        return {}


def _merge_sources_json(existing: str, patch: dict[str, Any]) -> str:
    base = _clean_json(existing)
    # Merge under stable key to avoid colliding with existing ingestion metadata.
    pc = base.get("pubchem")
    if not isinstance(pc, dict):
        pc = {}
    # Fill-only semantics: do not overwrite non-empty values.
    for k, v in patch.items():
        if k in pc and pc.get(k) not in (None, "", [], {}):
            continue
        pc[k] = v
    base["pubchem"] = pc
    return json.dumps(base, ensure_ascii=False, sort_keys=True)


def _request_json(session: requests.Session, url: str, *, timeout: float = 20.0) -> dict[str, Any] | None:
    retries = int(os.getenv("PUBCHEM_RETRIES", "5"))
    backoff = float(os.getenv("PUBCHEM_BACKOFF_SECONDS", "0.6"))
    sleep_seconds = float(os.getenv("PUBCHEM_SLEEP_SECONDS", "0.02"))

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        try:
            resp = session.get(url, timeout=timeout)
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
    return None


def _fetch_property_table(session: requests.Session, cids: list[int]) -> dict[int, dict[str, Any]]:
    if not cids:
        return {}
    cid_list = ",".join(str(int(c)) for c in cids)

    # Try a superset first; fall back if PubChem rejects properties.
    props_full = [
        "MolecularFormula",
        "MolecularWeight",
        "ExactMass",
        "IUPACName",
        "InChIKey",
        "CanonicalSMILES",
        "XLogP",
        "TPSA",
        "HBondDonorCount",
        "HBondAcceptorCount",
        "RotatableBondCount",
        "Complexity",
    ]
    props_min = [
        "MolecularFormula",
        "MolecularWeight",
        "ExactMass",
        "IUPACName",
        "InChIKey",
        "CanonicalSMILES",
    ]

    def _try(props: list[str]) -> dict[int, dict[str, Any]]:
        prop_list = ",".join(props)
        url = f"{PUBCHEM_BASE}/compound/cid/{cid_list}/property/{prop_list}/JSON"
        blob = _request_json(session, url, timeout=25.0)
        props_rows = (blob or {}).get("PropertyTable", {}).get("Properties", [])
        out: dict[int, dict[str, Any]] = {}
        if isinstance(props_rows, list):
            for row in props_rows:
                if not isinstance(row, dict):
                    continue
                cid = row.get("CID")
                try:
                    cid_i = int(cid)
                except Exception:
                    continue
                out[cid_i] = row
        return out

    try:
        out = _try(props_full)
        if out:
            return out
    except Exception:
        pass
    return _try(props_min)


def _fetch_pug_view(session: requests.Session, cid: int) -> dict[str, Any] | None:
    url = f"{PUBCHEM_BASE}/pug_view/data/compound/{int(cid)}/JSON"
    return _request_json(session, url, timeout=30.0)


def _select_cids_to_fetch(*, max_cids: int | None) -> list[int]:
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.PubChemTermMatch.cid)
            .filter(database_manager.PubChemTermMatch.status == "matched")
            .filter(database_manager.PubChemTermMatch.cid.isnot(None))
            .distinct()
        )
        cids = [int(r[0]) for r in q.all() if r and r[0] is not None]
    cids = sorted(set(cids))

    # Filter out CIDs already fetched (property bundle fetched_property_at populated).
    with database_manager.get_session() as session:
        existing = {
            int(r[0])
            for r in session.query(database_manager.PubChemCompound.cid)
            .filter(database_manager.PubChemCompound.cid.in_(cids))
            .filter(database_manager.PubChemCompound.fetched_property_at.isnot(None))
            .all()
        }
    remaining = [c for c in cids if c not in existing]
    if max_cids:
        return remaining[: int(max_cids)]
    return remaining


def _select_cids_missing_pug_view(*, max_cids: int | None) -> list[int]:
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.PubChemTermMatch.cid)
            .filter(database_manager.PubChemTermMatch.status == "matched")
            .filter(database_manager.PubChemTermMatch.cid.isnot(None))
            .distinct()
        )
        cids = [int(r[0]) for r in q.all() if r and r[0] is not None]
    cids = sorted(set(cids))
    with database_manager.get_session() as session:
        done = {
            int(r[0])
            for r in session.query(database_manager.PubChemCompound.cid)
            .filter(database_manager.PubChemCompound.cid.in_(cids))
            .filter(database_manager.PubChemCompound.fetched_pug_view_at.isnot(None))
            .all()
        }
    remaining = [c for c in cids if c not in done]
    if max_cids:
        return remaining[: int(max_cids)]
    return remaining


def _chunked(values: list[int], size: int) -> Iterable[list[int]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


def run(*, max_cids: int | None, batch_size: int, workers: int, fetch_pug_view: bool, apply_to_terms: bool) -> dict[str, int]:
    cids = _select_cids_to_fetch(max_cids=max_cids)
    cid_set = set(int(c) for c in cids)
    stats: dict[str, int] = {
        "cids_total_to_fetch": len(cids),
        "property_rows_cached": 0,
        "pug_view_cached": 0,
        "terms_updated": 0,
    }
    if not cids and not fetch_pug_view:
        return stats

    http = requests.Session()

    # 2A) PropertyTable (batchable)
    property_by_cid: dict[int, dict[str, Any]] = {}
    if cids:
        for batch in _chunked(cids, max(1, int(batch_size))):
            rows = _fetch_property_table(http, batch)
            property_by_cid.update(rows)

    now = datetime.now(timezone.utc)
    database_manager.ensure_tables_exist()
    if cids:
        with database_manager.get_session() as session:
            for cid in cids:
                rec = session.get(database_manager.PubChemCompound, int(cid))
                if rec is None:
                    rec = database_manager.PubChemCompound(cid=int(cid))
                    session.add(rec)
                rec.property_json = json.dumps(property_by_cid.get(int(cid), {}), ensure_ascii=False, sort_keys=True)
                if rec.pug_view_json is None:
                    rec.pug_view_json = "{}"
                rec.fetched_property_at = now
                stats["property_rows_cached"] += 1

    # 2B) PUG View (per CID, optional)
    if fetch_pug_view:
        pug_cids = _select_cids_missing_pug_view(max_cids=max_cids)
        def _one(cid: int) -> tuple[int, dict[str, Any] | None]:
            return int(cid), _fetch_pug_view(requests.Session(), int(cid))

        results: list[tuple[int, dict[str, Any] | None]] = []
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
            futs = [pool.submit(_one, int(cid)) for cid in pug_cids]
            for fut in as_completed(futs):
                results.append(fut.result())

        with database_manager.get_session() as session:
            for cid, blob in results:
                rec = session.get(database_manager.PubChemCompound, int(cid))
                if rec is None:
                    rec = database_manager.PubChemCompound(cid=int(cid))
                    session.add(rec)
                rec.pug_view_json = json.dumps(blob or {}, ensure_ascii=False)
                rec.fetched_pug_view_at = now
                stats["pug_view_cached"] += 1

    # Apply back onto normalized_terms.sources_json (fill-only), optional.
    if apply_to_terms:
        database_manager.ensure_tables_exist()
        with database_manager.get_session() as session:
            # Preload cached property JSON for quick access.
            cached: dict[int, dict[str, Any]] = {}
            for cid in cids:
                rec = session.get(database_manager.PubChemCompound, int(cid))
                if rec is None:
                    continue
                cached[int(cid)] = _clean_json(rec.property_json or "{}")

            q = session.query(database_manager.PubChemTermMatch).filter(database_manager.PubChemTermMatch.status == "matched")
            for match in q.yield_per(500):
                try:
                    cid = int(match.cid) if match.cid is not None else None
                except Exception:
                    cid = None
                if not cid:
                    continue
                # Only apply when the CID was part of this run's fetch set.
                if cid not in cid_set:
                    continue
                term_row = session.get(database_manager.NormalizedTerm, match.term)
                if term_row is None:
                    continue
                patch = {
                    "cid": cid,
                    "matched_by": match.matched_by,
                    "property": cached.get(cid, {}),
                }
                term_row.sources_json = _merge_sources_json(term_row.sources_json or "{}", patch)
                stats["terms_updated"] += 1

    return stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PubChem Stage 2: fetch & cache enrichment bundles for matched CIDs")
    p.add_argument("--max-cids", type=int, default=int(os.getenv("PUBCHEM_STAGE2_MAX_CIDS", "0")))
    p.add_argument("--batch-size", type=int, default=int(os.getenv("PUBCHEM_PROPERTY_BATCH_SIZE", "100")))
    p.add_argument("--workers", type=int, default=int(os.getenv("PUBCHEM_WORKERS", "16")))
    p.add_argument("--fetch-pug-view", action="store_true", help="Also fetch PUG View JSON per CID (slower)")
    p.add_argument("--apply-to-terms", action="store_true", help="Fill-only merge PubChem data into normalized_terms.sources_json")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    max_cids = int(args.max_cids) if int(args.max_cids or 0) > 0 else None
    stats = run(
        max_cids=max_cids,
        batch_size=max(1, int(args.batch_size or 100)),
        workers=max(1, int(args.workers or 1)),
        fetch_pug_view=bool(args.fetch_pug_view),
        apply_to_terms=bool(args.apply_to_terms),
    )
    LOGGER.info("pubchem stage2 stats: %s", stats)


if __name__ == "__main__":
    main()

