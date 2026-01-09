"""One-time pre-AI pipeline: sources -> ingestion -> PubChem enrichment.

This is the canonical A→Z deterministic pipeline stage. It:
- builds the ingestion DB from bundled CosIng + TGSC sources
- seeds the compiler queue from normalized_terms (DB->DB)
- matches items + terms to PubChem CIDs, fetches PubChem bundles, and applies fill-only specs

AI compilation (compiler.py) is intentionally NOT run here.
"""

from __future__ import annotations

import logging

from . import run_ingestion_pipeline
from . import run_pubchem_pipeline
from . import database_manager


def run() -> None:
    run_ingestion_pipeline.run()
    # PubChem is the last deterministic enrichment stage before AI.
    run_pubchem_pipeline.main(
        [
            "--mode",
            "full",
        ]
    )


def main() -> None:
    import argparse

    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    p = argparse.ArgumentParser(description="One-time deterministic pipeline (ingest -> pubchem), no AI")
    p.add_argument("--db-path", default="", help="SQLite DB path override (otherwise uses compiler_state.db)")
    args = p.parse_args()
    if (args.db_path or "").strip():
        database_manager.configure_db_path((args.db_path or "").strip())
    run()


if __name__ == "__main__":
    main()

