"""Deterministic PubChem enrichment pipeline (pre-AI).

This module is intentionally conservative:
- Match local entities to a single PubChem CID using available identifiers.
- Fetch PubChem properties in supported "bundles".
- Apply fill-only enrichment into `merged_item_forms.merged_specs_json` with provenance.

Why merged_item_forms?
- It's your ingestion-stage deduped "item identity" (derived_term + variation + physical_form).
- It already aggregates provenance across sources and is the best place for pre-AI enrichment.

PubChem API reality:
- PUG REST PropertyTable is batchable by CID list and returns computed/structured properties.
- PUG View experimental properties (density/solubility/mp/bp/etc.) are usually only accessible
  via per-CID JSON sections (not a single batched endpoint).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Iterable

import requests

from . import database_manager

LOGGER = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest"

# Throughput controls
DEFAULT_WORKERS = int(os.getenv("PUBCHEM_WORKERS", "16"))
SLEEP_SECONDS = float(os.getenv("PUBCHEM_SLEEP_SECONDS", "0"))
HTTP_TIMEOUT = float(os.getenv("PUBCHEM_HTTP_TIMEOUT", "15"))

MATCH_ENTITY_TYPE = "merged_item_form"


def _clean(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _json_loads(text: str, default: Any) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return default


def _now() -> datetime:
    return datetime.utcnow()


def _cas_tokens(value: str) -> list[str]:
    v = _clean(value)
    if not v:
        return []
    toks = re.findall(r"\b(\d{2,7}-\d{2}-\d)\b", v)
    seen: set[str] = set()
    out: list[str] = []
    for t in toks:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


class PubChemClient:
    def __init__(self) -> None:
        self.session = requests.Session()
        # Avoid urllib3 "Connection pool is full" warnings when using concurrency.
        try:  # pragma: no cover
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=max(10, DEFAULT_WORKERS * 2),
                pool_maxsize=max(10, DEFAULT_WORKERS * 2),
            )
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)
        except Exception:
            pass

    def _get_json(self, url: str, *, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        try:
            resp = self.session.get(url, params=params, timeout=HTTP_TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.debug("PubChem GET failed: %s (%s)", url, exc)
            return None

    def resolve_cids_by_identifier(self, *, identifier: str, identifier_type: str) -> list[int]:
        """Resolve identifier -> list[Cid]. Returns [] on no match."""
        ident = _clean(identifier)
        if not ident:
            return []

        # NOTE: PubChem supports several namespaces; keep it deterministic and simple.
        # - CAS: treat as "name" lookup (PubChem doesn't reliably support /rn/).
        # - INCI/raw term: name lookup.
        # - InChIKey: dedicated endpoint.
        if identifier_type == "inchikey":
            url = f"{PUBCHEM_BASE}/pug/compound/inchikey/{requests.utils.quote(ident)}/cids/JSON"
        elif identifier_type in {"cas", "name", "inci", "raw_name", "derived_term"}:
            url = f"{PUBCHEM_BASE}/pug/compound/name/{requests.utils.quote(ident)}/cids/JSON"
        else:
            return []

        blob = self._get_json(url)
        if not blob:
            return []
        cids = blob.get("IdentifierList", {}).get("CID", [])
        if not isinstance(cids, list):
            return []
        out: list[int] = []
        for c in cids:
            try:
                out.append(int(c))
            except Exception:
                continue
        return out

    def fetch_property_table(self, *, cids: list[int], props: list[str]) -> dict[int, dict[str, Any]]:
        """Batch fetch computed/structured properties. Returns cid -> property dict."""
        if not cids:
            return {}
        cid_list = ",".join(str(int(c)) for c in sorted(set(cids)))
        prop_list = ",".join(props)
        url = f"{PUBCHEM_BASE}/pug/compound/cid/{cid_list}/property/{prop_list}/JSON"
        blob = self._get_json(url)
        if not blob:
            return {}
        rows = blob.get("PropertyTable", {}).get("Properties", [])
        if not isinstance(rows, list):
            return {}
        out: dict[int, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = row.get("CID")
            try:
                cid_int = int(cid)
            except Exception:
                continue
            out[cid_int] = row
        return out

    def fetch_pug_view(self, *, cid: int) -> dict[str, Any] | None:
        url = f"{PUBCHEM_BASE}/pug_view/data/compound/{int(cid)}/JSON"
        return self._get_json(url)


# ----------------------------
# PUG View extraction helpers
# ----------------------------

def _iter_pugview_sections(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        if "TOCHeading" in node and "Information" in node:
            yield node
        for v in node.values():
            yield from _iter_pugview_sections(v)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_pugview_sections(item)


def _extract_first_text(section: dict[str, Any]) -> str:
    info = section.get("Information")
    if not isinstance(info, list):
        return ""
    for item in info:
        if not isinstance(item, dict):
            continue
        # Common: {"Value": {"StringWithMarkup": [{"String": "..."}]}}
        val = item.get("Value")
        if isinstance(val, dict):
            swm = val.get("StringWithMarkup")
            if isinstance(swm, list) and swm:
                s0 = swm[0]
                if isinstance(s0, dict):
                    text = _clean(s0.get("String"))
                    if text:
                        return text
        # Sometimes: {"Value": {"Number": [..]}} etc; ignore for now.
    return ""


def extract_experimental_text(pug_view_json: dict[str, Any] | None) -> dict[str, str]:
    """Best-effort extraction of experimental-ish text fields from PUG View."""
    if not isinstance(pug_view_json, dict):
        return {}
    wanted = {
        "Density": "density_text",
        "Solubility": "solubility_text",
        "Melting Point": "melting_point_text",
        "Boiling Point": "boiling_point_text",
        "Flash Point": "flash_point_text",
    }
    out: dict[str, str] = {}
    for sec in _iter_pugview_sections(pug_view_json):
        heading = _clean(sec.get("TOCHeading"))
        if heading not in wanted:
            continue
        txt = _extract_first_text(sec)
        if txt:
            out[wanted[heading]] = txt
    return out


# ----------------------------
# Matching (stage 1)
# ----------------------------

def _match_confidence(identifier_type: str) -> int:
    # Conservative heuristic (higher = better)
    return {
        "cas": 95,
        "inchikey": 95,
        "inci": 80,
        "name": 75,
        "derived_term": 70,
        "raw_name": 60,
    }.get(identifier_type, 50)


def _pick_representative_source_item(session, merged_row: database_manager.MergedItemForm) -> database_manager.SourceItem | None:
    keys = _json_loads(_clean(getattr(merged_row, "member_source_item_keys_json", "")) or "[]", [])
    if not isinstance(keys, list) or not keys:
        return None
    # Prefer CosIng row (often cleaner INCI)
    for key in keys:
        r = session.get(database_manager.SourceItem, str(key))
        if r is not None and (getattr(r, "source", "") or "").lower() == "cosing":
            return r
    # else first existing
    for key in keys:
        r = session.get(database_manager.SourceItem, str(key))
        if r is not None:
            return r
    return None


def match_merged_items(*, limit: int = 0, workers: int = DEFAULT_WORKERS) -> dict[str, int]:
    """Assign PubChem CID matches for merged_item_forms rows."""
    database_manager.ensure_tables_exist()
    client = PubChemClient()

    stats = {"scanned": 0, "matched": 0, "no_match": 0, "ambiguous": 0, "error": 0, "created_match_rows": 0}
    statuses_env = os.getenv("PUBCHEM_MATCH_STATUSES", "pending")
    match_statuses = {s.strip() for s in (statuses_env or "pending").split(",") if s.strip()} or {"pending"}

    with database_manager.get_session() as session:
        # Create missing match rows for each merged item.
        q = session.query(database_manager.MergedItemForm).order_by(database_manager.MergedItemForm.id.asc())
        if limit and int(limit) > 0:
            q = q.limit(int(limit))
        merged_rows = q.all()

        existing = {
            (r.entity_type, int(r.entity_id)): r
            for r in session.query(database_manager.PubChemItemMatch)
            .filter(database_manager.PubChemItemMatch.entity_type == MATCH_ENTITY_TYPE)
            .all()
        }

        for m in merged_rows:
            key = (MATCH_ENTITY_TYPE, int(m.id))
            if key in existing:
                continue
            session.add(database_manager.PubChemItemMatch(entity_type=MATCH_ENTITY_TYPE, entity_id=int(m.id), status="pending"))
            stats["created_match_rows"] += 1

    # Worker: resolve one entity id -> match row updates
    def _resolve_one(entity_id: int) -> tuple[int, dict[str, Any]]:
        with database_manager.get_session() as session:
            merged = session.get(database_manager.MergedItemForm, int(entity_id))
            if merged is None:
                return entity_id, {"status": "error", "error": "missing_merged_item"}

            rep = _pick_representative_source_item(session, merged)
            cas_list = _json_loads(_clean(getattr(merged, "cas_numbers_json", "")) or "[]", [])
            if not isinstance(cas_list, list):
                cas_list = []
            cas_list = [c for c in cas_list if _clean(c)]
            # Also extract CAS tokens from representative cas_number field just in case.
            if rep is not None and _clean(getattr(rep, "cas_number", "")):
                for c in _cas_tokens(_clean(getattr(rep, "cas_number", ""))):
                    if c not in cas_list:
                        cas_list.append(c)

            candidates: list[tuple[str, str]] = []
            for cas in cas_list:
                candidates.append(("cas", cas))

            # INCI/raw name (single representative)
            if rep is not None and _clean(getattr(rep, "inci_name", "")):
                candidates.append(("inci", _clean(getattr(rep, "inci_name", ""))))
            if rep is not None and _clean(getattr(rep, "raw_name", "")):
                candidates.append(("raw_name", _clean(getattr(rep, "raw_name", ""))))

            # Derived term from merged identity
            if _clean(getattr(merged, "derived_term", "")):
                candidates.append(("derived_term", _clean(getattr(merged, "derived_term", ""))))

        # Try identifiers in order; accept only unambiguous single CID
        last: tuple[str, str] | None = None
        for id_type, id_value in candidates:
            last = (id_type, id_value)
            cids = client.resolve_cids_by_identifier(identifier=id_value, identifier_type=id_type)
            if SLEEP_SECONDS:
                time.sleep(SLEEP_SECONDS)
            if not cids:
                continue
            if len(cids) == 1:
                return entity_id, {
                    "status": "matched",
                    "cid": int(cids[0]),
                    "matched_by": id_type,
                    "identifier_type": id_type,
                    "identifier_value": id_value,
                    "confidence": _match_confidence(id_type),
                    "candidate_cids_json": json.dumps(cids),
                    "error": None,
                }
            # multiple cids => ambiguous; record and stop (deterministic, no guessing)
            return entity_id, {
                "status": "ambiguous",
                "cid": None,
                "matched_by": id_type,
                "identifier_type": id_type,
                "identifier_value": id_value,
                "confidence": _match_confidence(id_type) - 20,
                "candidate_cids_json": json.dumps(cids[:50]),
                "error": f"ambiguous_candidates:{len(cids)}",
            }

        out: dict[str, Any] = {"status": "no_match", "candidate_cids_json": "[]", "error": None}
        if last is not None:
            out.update(
                {
                    "matched_by": last[0],
                    "identifier_type": last[0],
                    "identifier_value": last[1],
                    "confidence": _match_confidence(last[0]) - 40,
                }
            )
        return entity_id, out

    # Execute matching in parallel
    with database_manager.get_session() as session:
        pending_ids = [
            int(r.entity_id)
            for r in session.query(database_manager.PubChemItemMatch)
            .filter(database_manager.PubChemItemMatch.entity_type == MATCH_ENTITY_TYPE)
            .filter(database_manager.PubChemItemMatch.status.in_(sorted(match_statuses)))
            .all()
        ]

    if not pending_ids:
        return stats

    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
        futs = [ex.submit(_resolve_one, eid) for eid in pending_ids]
        for fut in as_completed(futs):
            eid, upd = fut.result()
            with database_manager.get_session() as session:
                row = (
                    session.query(database_manager.PubChemItemMatch)
                    .filter(database_manager.PubChemItemMatch.entity_type == MATCH_ENTITY_TYPE)
                    .filter(database_manager.PubChemItemMatch.entity_id == int(eid))
                    .first()
                )
                if row is None:
                    continue
                stats["scanned"] += 1
                row.status = upd.get("status") or row.status
                row.cid = upd.get("cid")
                row.matched_by = upd.get("matched_by")
                row.identifier_type = upd.get("identifier_type")
                row.identifier_value = upd.get("identifier_value")
                row.confidence = upd.get("confidence")
                row.candidate_cids_json = upd.get("candidate_cids_json") or row.candidate_cids_json
                row.error = upd.get("error")
                row.updated_at = _now()

                if row.status == "matched":
                    stats["matched"] += 1
                elif row.status == "no_match":
                    stats["no_match"] += 1
                elif row.status == "ambiguous":
                    stats["ambiguous"] += 1
                else:
                    stats["error"] += 1

    return stats


# ----------------------------
# Enrichment (stage 2) + apply
# ----------------------------

PROPERTY_BUNDLE = [
    "MolecularFormula",
    "MolecularWeight",
    "ExactMass",
    "IUPACName",
    "InChIKey",
    # PubChem sometimes returns ConnectivitySMILES instead of CanonicalSMILES depending on record.
    "CanonicalSMILES",
    "ConnectivitySMILES",
    "XLogP",
    "TPSA",
    "HBondDonorCount",
    "HBondAcceptorCount",
    "RotatableBondCount",
    "Complexity",
]


def _fill_only(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    out = dict(dst)
    for k, v in (src or {}).items():
        if k in out and _clean(out.get(k)) != "":
            continue
        out[k] = v
    return out


def _apply_pubchem_to_merged_item(
    session,
    *,
    merged: database_manager.MergedItemForm,
    cid: int,
    property_row: dict[str, Any] | None,
    extracted: dict[str, Any] | None,
) -> bool:
    """Fill-only apply into merged_specs_json and merged_specs_sources_json. Returns True if changed."""
    old_specs = _json_loads(_clean(getattr(merged, "merged_specs_json", "")) or "{}", {})
    old_sources = _json_loads(_clean(getattr(merged, "merged_specs_sources_json", "")) or "{}", {})
    if not isinstance(old_specs, dict):
        old_specs = {}
    if not isinstance(old_sources, dict):
        old_sources = {}

    updates: dict[str, Any] = {}
    # PropertyTable -> stable lowercase keys
    if isinstance(property_row, dict):
        mapping = {
            "MolecularFormula": "molecular_formula",
            "MolecularWeight": "molecular_weight",
            "ExactMass": "exact_mass",
            "IUPACName": "iupac_name",
            "InChIKey": "inchikey",
            "XLogP": "xlogp",
            "TPSA": "tpsa",
            "HBondDonorCount": "hbond_donor_count",
            "HBondAcceptorCount": "hbond_acceptor_count",
            "RotatableBondCount": "rotatable_bond_count",
            "Complexity": "complexity",
        }
        for pub_k, local_k in mapping.items():
            val = property_row.get(pub_k)
            if val is None or val == "":
                continue
            updates[local_k] = val
        smiles = property_row.get("CanonicalSMILES") or property_row.get("ConnectivitySMILES")
        if smiles is not None and smiles != "":
            updates["canonical_smiles"] = smiles

    if isinstance(extracted, dict):
        for k in ("density_text", "solubility_text", "melting_point_text", "boiling_point_text", "flash_point_text"):
            v = extracted.get(k)
            if _clean(v):
                updates[k] = v

    if not updates:
        return False

    new_specs = _fill_only(old_specs, updates)
    changed = new_specs != old_specs
    if not changed:
        return False

    # Record provenance only for keys we actually filled
    prov = f"pubchem(cid:{int(cid)})"
    new_sources = dict(old_sources)
    for k in updates.keys():
        if k in old_specs and _clean(old_specs.get(k)) != "":
            continue
        new_sources.setdefault(k, prov)

    merged.merged_specs_json = json.dumps(new_specs, ensure_ascii=False, sort_keys=True)
    merged.merged_specs_sources_json = json.dumps(new_sources, ensure_ascii=False, sort_keys=True)
    return True


def enrich_and_apply(*, workers: int = DEFAULT_WORKERS, batch_size: int = 100) -> dict[str, int]:
    """Fetch PubChem bundles for matched CIDs and apply to merged_item_forms."""
    database_manager.ensure_tables_exist()
    client = PubChemClient()

    stats = {
        "matched_rows": 0,
        "unique_cids": 0,
        "cached_property_rows": 0,
        "cached_pug_view": 0,
        "applied_items": 0,
        "skipped_items_no_change": 0,
        "errors": 0,
    }

    with database_manager.get_session() as session:
        matches = (
            session.query(database_manager.PubChemItemMatch)
            .filter(database_manager.PubChemItemMatch.entity_type == MATCH_ENTITY_TYPE)
            .filter(database_manager.PubChemItemMatch.status == "matched")
            .filter(database_manager.PubChemItemMatch.cid.isnot(None))
            .all()
        )
        stats["matched_rows"] = len(matches)
        cids = sorted({int(m.cid) for m in matches if m.cid is not None})
        stats["unique_cids"] = len(cids)

        cached = {int(r.cid) for r in session.query(database_manager.PubChemCompound.cid).all()}
        missing = [c for c in cids if c not in cached]

    # 2A) PropertyTable (batchable)
    property_rows: dict[int, dict[str, Any]] = {}
    for i in range(0, len(missing), max(1, int(batch_size))):
        chunk = missing[i : i + int(batch_size)]
        rows = client.fetch_property_table(cids=chunk, props=PROPERTY_BUNDLE)
        property_rows.update(rows)
        if SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS)

    # 2B) PUG View (per CID) - in parallel
    def _fetch_pug(cid: int) -> tuple[int, dict[str, Any] | None, dict[str, str]]:
        pv = client.fetch_pug_view(cid=cid)
        if SLEEP_SECONDS:
            time.sleep(SLEEP_SECONDS)
        extracted = extract_experimental_text(pv)
        return cid, pv, extracted

    pug_results: dict[int, tuple[dict[str, Any] | None, dict[str, str]]] = {}
    if missing:
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
            futs = [ex.submit(_fetch_pug, int(cid)) for cid in missing]
            for fut in as_completed(futs):
                cid, pv, extracted = fut.result()
                pug_results[int(cid)] = (pv, extracted)

    # Cache compounds
    with database_manager.get_session() as session:
        for cid in missing:
            prop = property_rows.get(int(cid))
            pv, extracted = pug_results.get(int(cid), (None, {}))
            rec = session.get(database_manager.PubChemCompound, int(cid))
            if rec is None:
                rec = database_manager.PubChemCompound(cid=int(cid))
                session.add(rec)
            if prop is not None:
                rec.property_json = json.dumps(prop, ensure_ascii=False, sort_keys=True)
                stats["cached_property_rows"] += 1
            if pv is not None:
                rec.pug_view_json = json.dumps(pv, ensure_ascii=False, sort_keys=True)
                stats["cached_pug_view"] += 1
            rec.extracted_json = json.dumps(extracted or {}, ensure_ascii=False, sort_keys=True)
            rec.fetched_at = _now()

    # Apply to merged_item_forms (fill-only)
    with database_manager.get_session() as session:
        # Build fast cid -> cached payload map from DB (ensures we use cached values even if pre-existing)
        compounds = {int(r.cid): r for r in session.query(database_manager.PubChemCompound).all()}

        for m in (
            session.query(database_manager.PubChemItemMatch)
            .filter(database_manager.PubChemItemMatch.entity_type == MATCH_ENTITY_TYPE)
            .filter(database_manager.PubChemItemMatch.status == "matched")
            .filter(database_manager.PubChemItemMatch.cid.isnot(None))
            .yield_per(1000)
        ):
            cid = int(m.cid)
            merged = session.get(database_manager.MergedItemForm, int(m.entity_id))
            if merged is None:
                continue
            comp = compounds.get(cid)
            if comp is None:
                continue
            prop = _json_loads(_clean(getattr(comp, "property_json", "")) or "{}", {})
            extracted = _json_loads(_clean(getattr(comp, "extracted_json", "")) or "{}", {})

            changed = _apply_pubchem_to_merged_item(session, merged=merged, cid=cid, property_row=prop, extracted=extracted)
            if changed:
                stats["applied_items"] += 1
            else:
                stats["skipped_items_no_change"] += 1

    return stats


def run_pipeline(*, match_limit: int = 0, workers: int = DEFAULT_WORKERS, batch_size: int = 100) -> dict[str, Any]:
    """Match then enrich+apply (single runner)."""
    mstats = match_merged_items(limit=match_limit, workers=workers)
    estats = enrich_and_apply(workers=workers, batch_size=batch_size)
    return {"match": mstats, "enrich": estats}

