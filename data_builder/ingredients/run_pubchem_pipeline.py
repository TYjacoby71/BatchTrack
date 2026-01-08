"""CLI runner for deterministic PubChem pipeline (pre-AI)."""

from __future__ import annotations

import argparse
import logging

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
    stats = pubchem_pipeline.run_pipeline(
        match_limit=int(args.match_limit or 0),
        workers=workers,
        batch_size=int(args.batch_size or 100),
    )
    logging.getLogger(__name__).info("pubchem pipeline stats: %s", stats)


if __name__ == "__main__":
    main()

