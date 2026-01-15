"""PubChem Stage 1: match normalized terms to PubChem CIDs (name-first).

This is a deterministic pre-AI step.

It:
- iterates `normalized_terms`
- tries identifiers in priority order (name-based first)
- resolves to PubChem CIDs using PUG REST
- stores results in `pubchem_term_matches`

Notes:
- We only accept a match when PubChem returns exactly 1 CID for the identifier.
- Multi-CID responses are marked `ambiguous` (no guessing).
- 0-CID responses are marked `no_match`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from . import database_manager

LOGGER = logging.getLogger(__name__)

PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


@dataclass(frozen=True)
class _MatchWorkItem:
    term: str
    inci_name: str
    botanical_name: str


@dataclass(frozen=True)
class _MatchResult:
    term: str
    status: str  # matched|no_match|ambiguous|error
    cid: Optional[int]
    matched_by: Optional[str]
    candidates: list[int]
    error: Optional[str]


def _clean(value: Any) -> str:
    return ("" if value is None else str(value)).strip()


def _resolve_name_to_cids(session: requests.Session, name: str, *, timeout: float = 15.0) -> list[int]:
    quoted = requests.utils.quote(name)
    url = f"{PUBCHEM_BASE}/compound/name/{quoted}/cids/JSON"
    retries = int(os.getenv("PUBCHEM_RETRIES", "4"))
    backoff = float(os.getenv("PUBCHEM_BACKOFF_SECONDS", "0.4"))
    sleep_seconds = float(os.getenv("PUBCHEM_SLEEP_SECONDS", "0.0"))

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        try:
            resp = session.get(url, timeout=timeout)
            # Treat "not found" and "bad request" as no-match (many INCI strings are not valid compound names).
            if resp.status_code in (400, 404):
                return []
            # Retry on throttling / server busy.
            if resp.status_code in (429, 503):
                time.sleep(backoff * attempt)
                continue
            resp.raise_for_status()

            blob = resp.json() if resp.content else {}
            cids = (blob or {}).get("IdentifierList", {}).get("CID", [])
            if isinstance(cids, list):
                return [int(c) for c in cids if isinstance(c, (int, str)) and str(c).strip().isdigit()]
            return []
        except Exception as exc:  # pylint: disable=broad-except
            last_exc = exc
            # Network hiccup or unexpected server response; retry a few times.
            time.sleep(backoff * attempt)
            continue

    if last_exc:
        raise last_exc
    return []


def _match_one(item: _MatchWorkItem) -> _MatchResult:
    http = requests.Session()
    try:
        # Name-first priority (as requested).
        candidates: list[tuple[str, str]] = []
        if _clean(item.inci_name):
            candidates.append(("inci_name", _clean(item.inci_name)))
        if _clean(item.term):
            candidates.append(("term", _clean(item.term)))
        if _clean(item.botanical_name):
            candidates.append(("botanical_name", _clean(item.botanical_name)))

        for matched_by, ident in candidates:
            cids = _resolve_name_to_cids(http, ident)
            if len(cids) == 1:
                return _MatchResult(
                    term=item.term,
                    status="matched",
                    cid=int(cids[0]),
                    matched_by=matched_by,
                    candidates=cids,
                    error=None,
                )
            if len(cids) > 1:
                return _MatchResult(
                    term=item.term,
                    status="ambiguous",
                    cid=None,
                    matched_by=matched_by,
                    candidates=cids[:50],
                    error=f"ambiguous_candidates:{len(cids)}",
                )

        return _MatchResult(term=item.term, status="no_match", cid=None, matched_by=None, candidates=[], error=None)
    except Exception as exc:  # pylint: disable=broad-except
        return _MatchResult(term=item.term, status="error", cid=None, matched_by=None, candidates=[], error=str(exc))


def _ensure_rows_exist(terms: list[str]) -> None:
    """Ensure pubchem_term_matches has a row per term (idempotent)."""
    if not terms:
        return
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        existing = {r[0] for r in session.query(database_manager.PubChemTermMatch.term).filter(database_manager.PubChemTermMatch.term.in_(terms)).all()}
        missing = [t for t in terms if t not in existing]
        for t in missing:
            session.add(database_manager.PubChemTermMatch(term=t, status="pending"))


def _select_work(limit: int | None, *, include_done: bool) -> list[_MatchWorkItem]:
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        q = (
            session.query(
                database_manager.NormalizedTerm.term,
                database_manager.NormalizedTerm.inci_name,
                database_manager.NormalizedTerm.botanical_name,
                database_manager.PubChemTermMatch.status,
            )
            .outerjoin(
                database_manager.PubChemTermMatch,
                database_manager.PubChemTermMatch.term == database_manager.NormalizedTerm.term,
            )
        )

        if not include_done:
            q = q.filter(
                (database_manager.PubChemTermMatch.term.is_(None))
                | (database_manager.PubChemTermMatch.status.in_(["pending", "error", "ambiguous"]))
            )

        q = q.order_by(database_manager.NormalizedTerm.term.asc())
        if limit:
            q = q.limit(int(limit))

        rows = q.all()

    work: list[_MatchWorkItem] = []
    for term, inci, botanical, _status in rows:
        t = _clean(term)
        if not t:
            continue
        work.append(_MatchWorkItem(term=t, inci_name=_clean(inci), botanical_name=_clean(botanical)))
    return work


def run(*, limit: int | None, workers: int, include_done: bool = False) -> dict[str, int]:
    work = _select_work(limit, include_done=include_done)
    terms = [w.term for w in work]
    _ensure_rows_exist(terms)

    stats: dict[str, int] = {"attempted": 0, "matched": 0, "no_match": 0, "ambiguous": 0, "error": 0}
    if not work:
        return stats

    # Network in threads, DB writes in main thread.
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = [pool.submit(_match_one, w) for w in work]
        results: list[_MatchResult] = []
        for fut in as_completed(futures):
            results.append(fut.result())

    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        for r in results:
            stats["attempted"] += 1
            stats[r.status] = stats.get(r.status, 0) + 1
            row = session.get(database_manager.PubChemTermMatch, r.term)
            if row is None:
                row = database_manager.PubChemTermMatch(term=r.term, status="pending")
                session.add(row)
            row.status = r.status
            row.cid = r.cid
            row.matched_by = r.matched_by
            row.candidates_json = json.dumps(r.candidates, ensure_ascii=False)
            row.error = r.error
            row.updated_at = datetime.now(timezone.utc)

    return stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PubChem Stage 1: match normalized terms to PubChem CIDs (name-first)")
    p.add_argument("--limit", type=int, default=int(os.getenv("PUBCHEM_STAGE1_LIMIT", "500")))
    p.add_argument("--workers", type=int, default=int(os.getenv("PUBCHEM_WORKERS", "16")))
    p.add_argument("--include-done", action="store_true", help="Also reprocess already matched terms")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    limit = int(args.limit) if int(args.limit or 0) > 0 else None
    stats = run(limit=limit, workers=int(args.workers or 1), include_done=bool(args.include_done))
    LOGGER.info("pubchem stage1 stats: %s", stats)


if __name__ == "__main__":
    main()

