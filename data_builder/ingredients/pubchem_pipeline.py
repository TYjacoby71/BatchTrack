"""Deterministic pre-AI PubChem pipeline.

This pipeline is intentionally strict:
- Resolve item identifiers -> PubChem CID (no guessing; ambiguous name matches are treated as no-match).
- Fetch PubChem data in attribute bundles:
  - PropertyTable (batchable by CID list)
  - PUG View (per CID; experimental properties are not returned via PropertyTable)
- Apply to `merged_item_forms.merged_specs_json` as fill-only (never overwrite existing values).
"""

from __future__ import annotations

import json
import logging
import os
import re
import random
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Iterable, Optional

import requests

from . import database_manager

LOGGER = logging.getLogger(__name__)


_PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_PUBCHEM_PUG_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"

_RATE_LOCK = Lock()
_LAST_REQUEST_AT = 0.0


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _safe_json_loads(text: str, default: Any) -> Any:
    try:
        return json.loads(text) if text else default
    except Exception:
        return default


def _is_cas(value: str) -> bool:
    return bool(re.fullmatch(r"\d{2,7}-\d{2}-\d", _clean(value)))


class PubChemClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.timeout = float(os.getenv("PUBCHEM_TIMEOUT_SECONDS", "25"))

    def _get_json(self, url: str) -> dict[str, Any] | None:
        retries = max(1, int(os.getenv("PUBCHEM_RETRIES", "8")))
        backoff = float(os.getenv("PUBCHEM_BACKOFF_SECONDS", "0.8"))
        min_interval = float(os.getenv("PUBCHEM_MIN_INTERVAL_SECONDS", "0.25"))

        def throttle() -> None:
            """Global throttle across threads/process-local calls.

            Replit and other hosted environments often share egress IPs; this keeps us from
            stampeding PubChem and getting 503'd/429'd.
            """
            global _LAST_REQUEST_AT  # pylint: disable=global-statement
            if min_interval <= 0:
                return
            with _RATE_LOCK:
                now = time.time()
                wait = (_LAST_REQUEST_AT + min_interval) - now
                if wait > 0:
                    time.sleep(wait)
                _LAST_REQUEST_AT = time.time()

        last_exc: Exception | None = None
        last_status: int | None = None
        for attempt in range(1, retries + 1):
            try:
                throttle()
                resp = self.session.get(url, timeout=self.timeout)
                last_status = int(resp.status_code)
                if resp.status_code in (400, 404):
                    return None
                if resp.status_code in (429, 503):
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and str(retry_after).strip().isdigit():
                        time.sleep(float(int(retry_after)))
                    else:
                        # Exponential backoff + jitter
                        time.sleep(backoff * attempt + random.random() * 0.25)
                    continue
                resp.raise_for_status()
                blob = resp.json()
                return blob if isinstance(blob, dict) else None
            except Exception as exc:  # pylint: disable=broad-except
                last_exc = exc
                # Retry transient errors; keep deterministic-ish with bounded jitter.
                time.sleep(backoff * attempt + random.random() * 0.25)
                continue

        # Exhausted retries: treat PubChem as unavailable, not "no-match".
        if last_status in (429, 503):
            LOGGER.warning("PubChem unavailable after retries (%s): %s", last_status, url)
            return None
        if last_exc:
            LOGGER.debug("PubChem request failed: %s (%s)", url, last_exc)
        return None

    def resolve_name_to_cids(self, name: str) -> list[int]:
        quoted = requests.utils.quote(_clean(name))
        if not quoted:
            return []
        blob = self._get_json(f"{_PUBCHEM_BASE}/compound/name/{quoted}/cids/JSON")
        cids = (blob or {}).get("IdentifierList", {}).get("CID", [])
        return [int(x) for x in cids if isinstance(x, (int, float, str)) and str(x).strip().isdigit()]

    def resolve_cas_to_cids(self, cas: str) -> list[int]:
        """Resolve CAS RN to CID using PubChem RN (registry number) xref endpoint."""
        cas_clean = _clean(cas)
        if not _is_cas(cas_clean):
            return []
        quoted = requests.utils.quote(cas_clean)
        blob = self._get_json(f"{_PUBCHEM_BASE}/compound/xref/rn/{quoted}/cids/JSON")
        cids = (blob or {}).get("IdentifierList", {}).get("CID", [])
        return [int(x) for x in cids if isinstance(x, (int, float, str)) and str(x).strip().isdigit()]

    def fetch_property_table(self, cids: list[int]) -> dict[int, dict[str, Any]]:
        if not cids:
            return {}
        cid_list = ",".join(str(int(c)) for c in cids)
        props = ",".join(
            [
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
        )
        blob = self._get_json(f"{_PUBCHEM_BASE}/compound/cid/{cid_list}/property/{props}/JSON")
        rows = (blob or {}).get("PropertyTable", {}).get("Properties", [])
        out: dict[int, dict[str, Any]] = {}
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            cid = r.get("CID")
            if cid is None:
                continue
            try:
                out[int(cid)] = dict(r)
            except Exception:
                continue
        return out

    def fetch_xrefs_rn(self, cid: int) -> dict[str, Any] | None:
        blob = self._get_json(f"{_PUBCHEM_BASE}/compound/cid/{int(cid)}/xrefs/RN/JSON")
        return blob or None

    def fetch_pug_view(self, cid: int) -> dict[str, Any] | None:
        return self._get_json(f"{_PUBCHEM_PUG_VIEW}/{int(cid)}/JSON")


def _extract_pug_view_strings(pug_view: dict[str, Any]) -> dict[str, str]:
    """Best-effort extraction of common experimental properties from PUG View JSON."""
    out: dict[str, str] = {}
    if not isinstance(pug_view, dict):
        return out

    # PUG View structure: Record -> Section[] -> ... each section may contain Information[] with StringWithMarkup.
    record = pug_view.get("Record") if isinstance(pug_view.get("Record"), dict) else {}
    sections = record.get("Section") if isinstance(record.get("Section"), list) else []

    def iter_sections(nodes: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
        for n in nodes:
            if not isinstance(n, dict):
                continue
            yield n
            subs = n.get("Section")
            if isinstance(subs, list):
                yield from iter_sections(subs)

    def section_title(sec: dict[str, Any]) -> str:
        return _clean(sec.get("TOCHeading") or sec.get("Name") or "")

    def info_strings(sec: dict[str, Any]) -> list[str]:
        info = sec.get("Information") if isinstance(sec.get("Information"), list) else []
        texts: list[str] = []
        for i in info:
            if not isinstance(i, dict):
                continue
            val = i.get("Value") if isinstance(i.get("Value"), dict) else {}
            swm = val.get("StringWithMarkup")
            if isinstance(swm, list) and swm and isinstance(swm[0], dict):
                s = _clean(swm[0].get("String") or "")
                if s:
                    texts.append(s)
        return texts

    wanted = {
        "Density": "density_text",
        "Solubility": "solubility_text",
        "Melting Point": "melting_point_text",
        "Boiling Point": "boiling_point_text",
        "Flash Point": "flash_point_text",
        "pKa": "pka_text",
        "Dissociation Constants": "pka_text",
    }

    for sec in iter_sections(sections):
        title = section_title(sec)
        if not title:
            continue
        key = wanted.get(title)
        if not key:
            continue
        texts = info_strings(sec)
        if texts:
            out[key] = "; ".join(texts[:3])  # keep small & deterministic
    return out


def _merge_fill_only(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Fill-only merge: only set keys that are missing/blank in base."""
    out = dict(base)
    for k, v in patch.items():
        if k in out and out.get(k) not in (None, "", [], {}, "null"):
            continue
        if v in (None, "", [], {}, "null"):
            continue
        out[k] = v
    return out


def stage_and_match_items(*, limit: int | None = None) -> dict[str, int]:
    """Stage + resolve merged_item_forms to PubChem CIDs.

    Returns counts for observability.
    """
    database_manager.ensure_tables_exist()
    matched = 0
    no_match = 0
    error = 0
    scanned = 0  # number of unprocessed items staged for matching (this run)
    workers = max(1, int(os.getenv("PUBCHEM_WORKERS", "16")))
    cache: dict[str, list[int]] = {}
    cache_lock = Lock()

    # Phase 1: load worklist (avoid holding DB locks during network calls)
    work: list[dict[str, Any]] = []
    with database_manager.get_session() as session:
        q = session.query(database_manager.MergedItemForm).order_by(database_manager.MergedItemForm.id.asc())
        for item in q.yield_per(500):
            existing = session.get(database_manager.PubChemItemMatch, int(item.id))
            if existing and _clean(existing.status) in {"matched", "no_match"}:
                continue
            if limit and len(work) >= int(limit):
                break

            # Gather identifiers (pull term fields once, outside workers)
            identifiers: list[tuple[str, str, int]] = []
            cas_list = _safe_json_loads(_clean(item.cas_numbers_json), [])
            cas_candidates = [c for c in cas_list if isinstance(c, str) and _is_cas(c)]
            for cas in cas_candidates[:3]:
                identifiers.append(("cas", cas, 95))

            nt = (
                session.query(database_manager.NormalizedTerm)
                .filter(database_manager.NormalizedTerm.term == item.derived_term)
                .first()
            )
            if nt is not None:
                if _is_cas(_clean(nt.cas_number)):
                    identifiers.append(("cas", _clean(nt.cas_number), 95))
                if _clean(nt.inci_name):
                    identifiers.append(("inci", _clean(nt.inci_name), 75))
                if _clean(nt.botanical_name):
                    identifiers.append(("botanical", _clean(nt.botanical_name), 55))

            if _clean(item.derived_term):
                identifiers.append(("term", _clean(item.derived_term), 55))

            work.append({"id": int(item.id), "identifiers": identifiers})
    scanned = len(work)

    def _resolve_one(entry: dict[str, Any]) -> dict[str, Any]:
        client = PubChemClient()
        identifiers = entry.get("identifiers") or []
        last_err = None
        for kind, ident, conf in identifiers:
            key = f"{kind}:{ident}".lower()
            with cache_lock:
                if key in cache:
                    cids = cache[key]
                else:
                    cids = None
            if cids is None:
                if kind == "cas" and _is_cas(ident):
                    cids = client.resolve_cas_to_cids(ident)
                else:
                    cids = client.resolve_name_to_cids(ident)
                with cache_lock:
                    cache[key] = cids
            if not cids:
                continue
            if len(cids) != 1:
                last_err = f"ambiguous_candidates:{len(cids)}"
                continue
            return {
                "id": entry["id"],
                "status": "matched",
                "cid": int(cids[0]),
                "matched_by": kind,
                "identifier_value": ident,
                "confidence": int(conf),
                "error": None,
            }
        return {"id": entry["id"], "status": "no_match", "cid": None, "matched_by": None, "identifier_value": None, "confidence": None, "error": last_err}

    results: list[dict[str, Any]] = []
    if work:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_resolve_one, e) for e in work]
            for f in as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as exc:  # pylint: disable=broad-except
                    results.append({"id": None, "status": "error", "cid": None, "matched_by": None, "identifier_value": None, "confidence": None, "error": str(exc)})

    # Phase 2: write results to DB in one session
    with database_manager.get_session() as session:
        for r in results:
            mid = r.get("id")
            if not mid:
                error += 1
                continue
            row = session.get(database_manager.PubChemItemMatch, int(mid))
            if row is None:
                row = database_manager.PubChemItemMatch(merged_item_form_id=int(mid), status="pending")
                session.add(row)
            row.status = r["status"]
            row.cid = r.get("cid")
            row.matched_by = r.get("matched_by")
            row.identifier_value = r.get("identifier_value")
            row.confidence = r.get("confidence")
            row.error = r.get("error")
            row.matched_at = datetime.utcnow()
            if row.status == "matched":
                matched += 1
            elif row.status == "no_match":
                no_match += 1
            else:
                error += 1

    return {"scanned": scanned, "matched": matched, "no_match": no_match, "error": error}


def stage_and_match_terms(*, limit: int | None = None) -> dict[str, int]:
    """Stage + resolve normalized_terms to PubChem CIDs (strict; no guessing)."""
    database_manager.ensure_tables_exist()
    matched = 0
    no_match = 0
    error = 0
    scanned = 0  # number of unprocessed terms staged for matching (this run)
    workers = max(1, int(os.getenv("PUBCHEM_WORKERS", "16")))
    cache: dict[str, list[int]] = {}
    cache_lock = Lock()

    work: list[dict[str, Any]] = []
    with database_manager.get_session() as session:
        q = session.query(database_manager.NormalizedTerm).order_by(database_manager.NormalizedTerm.term.asc())
        for t in q.yield_per(500):
            existing = session.get(database_manager.PubChemTermMatch, str(t.term))
            if existing and _clean(existing.status) in {"matched", "no_match"}:
                continue
            if limit and len(work) >= int(limit):
                break
            identifiers: list[tuple[str, str, int]] = []
            if _is_cas(_clean(t.cas_number)):
                identifiers.append(("cas", _clean(t.cas_number), 95))
            if _clean(t.inci_name):
                identifiers.append(("inci", _clean(t.inci_name), 75))
            if _clean(t.botanical_name):
                identifiers.append(("botanical", _clean(t.botanical_name), 55))
            identifiers.append(("term", _clean(t.term), 55))
            work.append({"term": str(t.term), "identifiers": identifiers})
    scanned = len(work)

    def _resolve_one_term(entry: dict[str, Any]) -> dict[str, Any]:
        client = PubChemClient()
        identifiers = entry.get("identifiers") or []
        last_err = None
        for kind, ident, conf in identifiers:
            key = f"{kind}:{ident}".lower()
            with cache_lock:
                if key in cache:
                    cids = cache[key]
                else:
                    cids = None
            if cids is None:
                if kind == "cas" and _is_cas(ident):
                    cids = client.resolve_cas_to_cids(ident)
                else:
                    cids = client.resolve_name_to_cids(ident)
                with cache_lock:
                    cache[key] = cids
            if not cids:
                continue
            if len(cids) != 1:
                last_err = f"ambiguous_candidates:{len(cids)}"
                continue
            return {
                "term": entry["term"],
                "status": "matched",
                "cid": int(cids[0]),
                "matched_by": kind,
                "identifier_value": ident,
                "confidence": int(conf),
                "error": None,
            }
        return {"term": entry["term"], "status": "no_match", "cid": None, "matched_by": None, "identifier_value": None, "confidence": None, "error": last_err}

    results: list[dict[str, Any]] = []
    if work:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_resolve_one_term, e) for e in work]
            for f in as_completed(futures):
                try:
                    results.append(f.result())
                except Exception as exc:  # pylint: disable=broad-except
                    results.append({"term": None, "status": "error", "cid": None, "matched_by": None, "identifier_value": None, "confidence": None, "error": str(exc)})

    with database_manager.get_session() as session:
        for r in results:
            t = r.get("term")
            if not t:
                error += 1
                continue
            row = session.get(database_manager.PubChemTermMatch, str(t))
            if row is None:
                row = database_manager.PubChemTermMatch(term=str(t), status="pending")
                session.add(row)
            row.status = r["status"]
            row.cid = r.get("cid")
            row.matched_by = r.get("matched_by")
            row.identifier_value = r.get("identifier_value")
            row.confidence = r.get("confidence")
            row.error = r.get("error")
            row.matched_at = datetime.utcnow()
            if row.status == "matched":
                matched += 1
            elif row.status == "no_match":
                no_match += 1
            else:
                error += 1

    return {"scanned": scanned, "matched": matched, "no_match": no_match, "error": error}

def fetch_and_cache_pubchem(*, max_cids: int | None = None, batch_size: int = 100) -> dict[str, int]:
    """Fetch PubChem bundles for matched CIDs and cache them in pubchem_compounds."""
    database_manager.ensure_tables_exist()
    client = PubChemClient()

    fetched_property = 0
    fetched_pug_view = 0
    skipped_cached = 0

    with database_manager.get_session() as session:
        cid_rows_items = (
            session.query(database_manager.PubChemItemMatch.cid)
            .filter(database_manager.PubChemItemMatch.status == "matched", database_manager.PubChemItemMatch.cid.isnot(None))
            .distinct()
            .all()
        )
        cid_rows_terms = (
            session.query(database_manager.PubChemTermMatch.cid)
            .filter(database_manager.PubChemTermMatch.status == "matched", database_manager.PubChemTermMatch.cid.isnot(None))
            .distinct()
            .all()
        )
        cids = sorted(
            {int(r[0]) for r in (cid_rows_items + cid_rows_terms) if r and r[0] is not None}
        )
        if max_cids:
            cids = cids[: int(max_cids)]

        # PropertyTable: batchable
        for i in range(0, len(cids), int(batch_size)):
            batch = cids[i : i + int(batch_size)]
            to_fetch = []
            for cid in batch:
                rec = session.get(database_manager.PubChemCompound, int(cid))
                if rec is None:
                    to_fetch.append(cid)
                else:
                    pj = _safe_json_loads(_clean(rec.property_json), {})
                    if not pj:
                        to_fetch.append(cid)
                    else:
                        skipped_cached += 1
            if not to_fetch:
                continue
            props = client.fetch_property_table(to_fetch)
            for cid, row in props.items():
                rec = session.get(database_manager.PubChemCompound, int(cid))
                if rec is None:
                    rec = database_manager.PubChemCompound(cid=int(cid))
                    session.add(rec)
                rec.property_json = json.dumps(row, ensure_ascii=False, sort_keys=True)
                rec.fetched_property_at = datetime.utcnow()
                fetched_property += 1

        # PUG View: per CID (cache)
        for cid in cids:
            rec = session.get(database_manager.PubChemCompound, int(cid))
            if rec is None:
                rec = database_manager.PubChemCompound(cid=int(cid))
                session.add(rec)
            pv = _safe_json_loads(_clean(rec.pug_view_json), {})
            if pv:
                continue
            blob = client.fetch_pug_view(int(cid))
            if not blob:
                # Keep empty JSON but mark time so we don't hammer repeatedly.
                rec.pug_view_json = "{}"
                rec.fetched_pug_view_at = datetime.utcnow()
                continue
            rec.pug_view_json = json.dumps(blob, ensure_ascii=False, sort_keys=True)
            rec.fetched_pug_view_at = datetime.utcnow()
            fetched_pug_view += 1

        # CAS xrefs (optional, per CID)
        for cid in cids:
            rec = session.get(database_manager.PubChemCompound, int(cid))
            if rec is None:
                continue
            xr = _safe_json_loads(_clean(rec.xrefs_rn_json), {})
            if xr:
                continue
            blob = client.fetch_xrefs_rn(int(cid))
            rec.xrefs_rn_json = json.dumps(blob or {}, ensure_ascii=False, sort_keys=True)

    return {
        "unique_cids": len(cids),
        "fetched_property": fetched_property,
        "fetched_pug_view": fetched_pug_view,
        "skipped_cached_property": skipped_cached,
    }


def apply_pubchem_to_items(*, limit: int | None = None) -> dict[str, int]:
    """Fill-only apply cached PubChem data into merged_item_forms.merged_specs_json."""
    database_manager.ensure_tables_exist()
    applied = 0
    missing_cache = 0
    scanned = 0

    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.PubChemItemMatch)
            .filter(database_manager.PubChemItemMatch.status == "matched", database_manager.PubChemItemMatch.cid.isnot(None))
            .order_by(database_manager.PubChemItemMatch.merged_item_form_id.asc())
        )
        for m in q.yield_per(250):
            if limit and scanned >= int(limit):
                break
            scanned += 1

            item = session.get(database_manager.MergedItemForm, int(m.merged_item_form_id))
            if item is None:
                continue
            rec = session.get(database_manager.PubChemCompound, int(m.cid))
            if rec is None:
                missing_cache += 1
                continue

            specs = _safe_json_loads(_clean(item.merged_specs_json), {})
            sources = _safe_json_loads(_clean(item.merged_specs_sources_json), {})

            prop = _safe_json_loads(_clean(rec.property_json), {})
            pv = _safe_json_loads(_clean(rec.pug_view_json), {})
            pv_extracted = _extract_pug_view_strings(pv)

            patch = {
                "pubchem_cid": int(m.cid),
                "inchi_key": prop.get("InChIKey"),
                # PubChem PropertyTable sometimes returns SMILES under different keys depending on
                # property selection/serialization. Prefer CanonicalSMILES, then fall back.
                "canonical_smiles": prop.get("CanonicalSMILES") or prop.get("ConnectivitySMILES") or prop.get("IsomericSMILES"),
                "molecular_formula": prop.get("MolecularFormula"),
                "molecular_weight": prop.get("MolecularWeight"),
                "exact_mass": prop.get("ExactMass"),
                "iupac_name": prop.get("IUPACName"),
                "xlogp": prop.get("XLogP"),
                "tpsa": prop.get("TPSA"),
                "h_bond_donor_count": prop.get("HBondDonorCount"),
                "h_bond_acceptor_count": prop.get("HBondAcceptorCount"),
                "rotatable_bond_count": prop.get("RotatableBondCount"),
                "complexity": prop.get("Complexity"),
            }
            patch.update(pv_extracted)

            merged = _merge_fill_only(specs if isinstance(specs, dict) else {}, patch)

            # Record provenance (separate from specs keys).
            pubchem_src = {
                "cid": int(m.cid),
                "matched_by": m.matched_by,
                "confidence": int(m.confidence) if m.confidence is not None else None,
                "identifier_value": m.identifier_value,
                "applied_at": datetime.utcnow().isoformat(),
            }
            sources = dict(sources) if isinstance(sources, dict) else {}
            sources.setdefault("pubchem", pubchem_src)

            if merged != specs:
                item.merged_specs_json = json.dumps(merged, ensure_ascii=False, sort_keys=True)
                item.merged_specs_sources_json = json.dumps(sources, ensure_ascii=False, sort_keys=True)
                applied += 1

    return {"scanned": scanned, "applied": applied, "missing_cache": missing_cache}


def apply_pubchem_to_terms(*, limit: int | None = None) -> dict[str, int]:
    """Fill-only apply cached PubChem data into normalized_terms.sources_json (under sources_json['pubchem'])."""
    database_manager.ensure_tables_exist()
    applied = 0
    missing_cache = 0
    scanned = 0

    with database_manager.get_session() as session:
        q = (
            session.query(database_manager.PubChemTermMatch)
            .filter(database_manager.PubChemTermMatch.status == "matched", database_manager.PubChemTermMatch.cid.isnot(None))
            .order_by(database_manager.PubChemTermMatch.term.asc())
        )
        for m in q.yield_per(250):
            if limit and scanned >= int(limit):
                break
            scanned += 1

            term_row = session.get(database_manager.NormalizedTerm, str(m.term))
            if term_row is None:
                continue
            rec = session.get(database_manager.PubChemCompound, int(m.cid))
            if rec is None:
                missing_cache += 1
                continue

            sources = _safe_json_loads(_clean(term_row.sources_json), {})
            sources = dict(sources) if isinstance(sources, dict) else {}
            if "pubchem" in sources:
                continue  # already applied

            prop = _safe_json_loads(_clean(rec.property_json), {})
            pv = _safe_json_loads(_clean(rec.pug_view_json), {})
            pv_extracted = _extract_pug_view_strings(pv)

            sources["pubchem"] = {
                "cid": int(m.cid),
                "matched_by": m.matched_by,
                "confidence": int(m.confidence) if m.confidence is not None else None,
                "identifier_value": m.identifier_value,
                "applied_at": datetime.utcnow().isoformat(),
                "InChIKey": prop.get("InChIKey"),
                "MolecularFormula": prop.get("MolecularFormula"),
                "MolecularWeight": prop.get("MolecularWeight"),
                "ExactMass": prop.get("ExactMass"),
                "IUPACName": prop.get("IUPACName"),
                "CanonicalSMILES": prop.get("CanonicalSMILES") or prop.get("ConnectivitySMILES") or prop.get("IsomericSMILES"),
                **pv_extracted,
            }
            term_row.sources_json = json.dumps(sources, ensure_ascii=False, sort_keys=True)
            applied += 1

    return {"scanned": scanned, "applied": applied, "missing_cache": missing_cache}

