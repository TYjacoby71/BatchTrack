"""Canonical pre-AI pipeline runner (ONE supported path).

This is the single supported CLI entrypoint for the data builder *before AI*.

Design goals:
- One path (no running individual stage scripts directly).
- Deterministic, resume-safe, and reviewable between stages.
- Works in hosted environments (e.g. Replit) via throttling + bounded concurrency.

Stages:
- ingest: build the deterministic DB from bundled CosIng + TGSC sources (no AI).
- pubchem_match: Stage 1: match items/terms -> PubChem CID (bucketed: matched/no_match/ambiguous/retry).
- pubchem_retry: Stage 1 retry pass: only process retry bucket (rate-limit/transient), max 3 runs by default.
- pubchem_fetch: Stage 2: fetch/cache PubChem bundles for matched CIDs.
- pubchem_apply: Stage 3: fill-only apply cached PubChem fields back into seed specs.

AI compilation (compiler.py) is intentionally NOT run here.
"""

from __future__ import annotations

import argparse
import logging
import os

from . import database_manager, run_ingestion_pipeline, run_pubchem_pipeline

LOGGER = logging.getLogger(__name__)


def _configure_pubchem_env(args: argparse.Namespace) -> None:
    if args.pubchem_workers is not None:
        os.environ["PUBCHEM_WORKERS"] = str(int(args.pubchem_workers))
    if args.pubchem_min_interval is not None:
        os.environ["PUBCHEM_MIN_INTERVAL_SECONDS"] = str(float(args.pubchem_min_interval))
    if args.pubchem_retries is not None:
        os.environ["PUBCHEM_RETRIES"] = str(int(args.pubchem_retries))
    if args.pubchem_backoff is not None:
        os.environ["PUBCHEM_BACKOFF_SECONDS"] = str(float(args.pubchem_backoff))
    if args.pubchem_max_retry_runs is not None:
        os.environ["PUBCHEM_MAX_RETRY_RUNS"] = str(int(args.pubchem_max_retry_runs))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Canonical pre-AI pipeline (ONE supported path)")
    p.add_argument("--db-path", default="", help="SQLite DB path override (otherwise uses Final DB.db)")
    p.add_argument(
        "--stage",
        default="all",
        choices=[
            "ingest",
            "pubchem_match",
            "pubchem_retry",
            "pubchem_fetch",
            "pubchem_apply",
            "all",
        ],
        help="Which pre-AI stage to run.",
    )

    # PubChem knobs (kept here so you never need to run other scripts).
    p.add_argument("--match-limit", type=int, default=0, help="Max merged_item_forms to match this run (0 = no limit)")
    p.add_argument("--term-match-limit", type=int, default=0, help="Max normalized_terms to match this run (0 = no limit)")
    p.add_argument("--max-cids", type=int, default=0, help="Cap unique CIDs to fetch (0 = no cap)")
    p.add_argument("--batch-size", type=int, default=100, help="PropertyTable CID batch size")

    p.add_argument("--pubchem-workers", type=int, default=None, help="Thread workers for PubChem stages (default: env PUBCHEM_WORKERS or 16)")
    p.add_argument("--pubchem-min-interval", type=float, default=None, help="Global min seconds between HTTP calls (recommended for Replit)")
    p.add_argument("--pubchem-retries", type=int, default=None, help="Retries per HTTP call")
    p.add_argument("--pubchem-backoff", type=float, default=None, help="Backoff base seconds for 429/503/transient errors")
    p.add_argument("--pubchem-max-retry-runs", type=int, default=None, help="Max retry runs before downgrade retry->no_match (default: 3)")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    if (args.db_path or "").strip():
        database_manager.configure_db_path((args.db_path or "").strip())
    _configure_pubchem_env(args)

    stage = str(args.stage)
    match_limit = int(args.match_limit) if int(args.match_limit or 0) > 0 else 0
    term_match_limit = int(args.term_match_limit) if int(args.term_match_limit or 0) > 0 else 0
    max_cids = int(args.max_cids) if int(args.max_cids or 0) > 0 else 0
    batch_size = int(args.batch_size or 100)

    if stage in {"ingest", "all"}:
        run_ingestion_pipeline.run()

    # PubChem stages (deterministic pre-AI)
    if stage in {"pubchem_match", "all"}:
        run_pubchem_pipeline.main(
            [
                "--mode",
                "match_only",
                "--match-limit",
                str(match_limit),
                "--term-match-limit",
                str(term_match_limit),
            ]
        )

    if stage == "pubchem_retry":
        run_pubchem_pipeline.main(
            [
                "--mode",
                "match_only",
                "--retry-only",
                "--match-limit",
                str(match_limit),
                "--term-match-limit",
                str(term_match_limit),
            ]
        )

    if stage in {"pubchem_fetch", "all"}:
        run_pubchem_pipeline.main(
            [
                "--mode",
                "fetch_only",
                "--max-cids",
                str(max_cids),
                "--batch-size",
                str(batch_size),
            ]
        )

    if stage in {"pubchem_apply", "all"}:
        run_pubchem_pipeline.main(
            [
                "--mode",
                "apply_only",
            ]
        )

    LOGGER.info("pre-ai pipeline stage complete: %s (db=%s)", stage, database_manager.DB_PATH)


if __name__ == "__main__":
    main()

