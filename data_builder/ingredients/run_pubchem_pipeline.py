"""Run the deterministic pre-AI PubChem pipeline (one command).

Stages:
1) Match: assign PubChem CID to each merged_item_form (strict; no guessing).
   Also match normalized terms (strict; no guessing).
2) Fetch: cache PubChem bundles by CID (PropertyTable batch + PUG View per CID).
3) Apply: fill-only into merged_item_forms.merged_specs_json (+ provenance).
   Also apply into normalized_terms.sources_json['pubchem'] (+ provenance).
"""

from __future__ import annotations

import argparse
import logging

from . import pubchem_pipeline
from . import database_manager


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Deterministic PubChem pipeline (match -> fetch -> apply)")
    p.add_argument("--db-path", default="", help="SQLite DB path override (otherwise uses compiler_state.db)")
    p.add_argument("--mode", default="full", choices=["match_only", "fetch_only", "apply_only", "full"])
    p.add_argument("--match-limit", type=int, default=0, help="Max merged_item_forms to match (0 = no limit)")
    p.add_argument("--term-match-limit", type=int, default=0, help="Max normalized_terms to match (0 = no limit)")
    p.add_argument("--apply-limit", type=int, default=0, help="Max matched items to apply (0 = no limit)")
    p.add_argument("--term-apply-limit", type=int, default=0, help="Max matched terms to apply (0 = no limit)")
    p.add_argument("--max-cids", type=int, default=0, help="Cap unique CIDs to fetch (0 = no cap)")
    p.add_argument("--batch-size", type=int, default=100, help="PropertyTable CID batch size")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    args = parse_args(argv)
    if (args.db_path or "").strip():
        database_manager.configure_db_path((args.db_path or "").strip())

    match_limit = int(args.match_limit) if int(args.match_limit or 0) > 0 else None
    term_match_limit = int(args.term_match_limit) if int(args.term_match_limit or 0) > 0 else None
    apply_limit = int(args.apply_limit) if int(args.apply_limit or 0) > 0 else None
    term_apply_limit = int(args.term_apply_limit) if int(args.term_apply_limit or 0) > 0 else None
    max_cids = int(args.max_cids) if int(args.max_cids or 0) > 0 else None
    batch_size = int(args.batch_size or 100)

    if args.mode in {"match_only", "full"}:
        stats_items = pubchem_pipeline.stage_and_match_items(limit=match_limit)
        stats_terms = pubchem_pipeline.stage_and_match_terms(limit=term_match_limit)
        logging.getLogger(__name__).info("pubchem match items: %s", stats_items)
        logging.getLogger(__name__).info("pubchem match terms: %s", stats_terms)

    if args.mode in {"fetch_only", "full"}:
        stats = pubchem_pipeline.fetch_and_cache_pubchem(max_cids=max_cids, batch_size=batch_size)
        logging.getLogger(__name__).info("pubchem fetch: %s", stats)

    if args.mode in {"apply_only", "full"}:
        stats_items = pubchem_pipeline.apply_pubchem_to_items(limit=apply_limit)
        stats_terms = pubchem_pipeline.apply_pubchem_to_terms(limit=term_apply_limit)
        logging.getLogger(__name__).info("pubchem apply items: %s", stats_items)
        logging.getLogger(__name__).info("pubchem apply terms: %s", stats_terms)


if __name__ == "__main__":
    main()

