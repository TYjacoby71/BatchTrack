"""CLI runner for deterministic PubChem pipeline (pre-AI).

This mirrors the flow in your transcript:
- Stage 1 (match): assign PubChem CID to each seed item
- Stage 2 (enrich): fetch PropertyTable bundles (batch) + PUG View (per CID) and apply fill-only

Control is via environment variables:
- PUBCHEM_PIPELINE_MODE=match_only|full (default full)
- PUBCHEM_MATCH_STATUSES=pending[,no_match,error,...] (default pending)
- PUBCHEM_WORKERS, PUBCHEM_SLEEP_SECONDS
"""

from __future__ import annotations

import argparse
import logging
import os

from . import pubchem_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run deterministic PubChem match+enrich against merged item forms")
    p.add_argument("--match-limit", type=int, default=0, help="Optional cap for how many merged items to match this run")
    p.add_argument("--workers", type=int, default=0, help="Override PUBCHEM_WORKERS")
    p.add_argument("--batch-size", type=int, default=100, help="PropertyTable batch size (CIDs per request)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    workers = int(args.workers) if int(args.workers or 0) > 0 else pubchem_pipeline.DEFAULT_WORKERS
    mode = (os.getenv("PUBCHEM_PIPELINE_MODE", "full") or "full").strip().lower()
    if mode == "match_only":
        stats = {"match": pubchem_pipeline.match_seed_items(limit=int(args.match_limit or 0), workers=workers)}
    else:
        # Stage 2 only: enrichment/apply for already-matched items.
        stats = {"enrich": pubchem_pipeline.enrich_and_apply(workers=workers, batch_size=int(args.batch_size or 100))}
    logging.getLogger(__name__).info("pubchem pipeline stats: %s", stats)


if __name__ == "__main__":
    main()

