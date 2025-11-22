"""Orchestrator CLI for the ingredient data builder."""
from __future__ import annotations

import argparse
import logging
from typing import List

from .ai_worker import AIWorker
from .config import load_settings
from .schema import IngredientPayload
from .state import (
    STATUS_COMPLETED,
    STATUS_ERROR,
    STATUS_PENDING,
    STATUS_PROCESSING,
    StateStore,
)
from .storage import persist_payload

logger = logging.getLogger(__name__)


def process_terms(terms: List[str]) -> None:
    settings = load_settings()
    store = StateStore(settings.db_path)
    worker = AIWorker(settings)

    if not terms:
        logger.info("No pending terms found. Queue is empty or already processed.")
        return

    for term in terms:
        logger.info("Processing term '%s'", term)
        store.mark_status(term, STATUS_PROCESSING)
        try:
            result = worker.generate(term)
            target = persist_payload(result.payload, settings.output_dir)
            store.mark_status(term, STATUS_COMPLETED)
            logger.info(
                "✓ %s written to %s via %s", term, target.relative_to(settings.project_root), result.source
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to process %s", term)
            store.mark_status(term, STATUS_ERROR, str(exc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process ingredient queue entries")
    parser.add_argument(
        "--batch", type=int, default=10, help="Number of pending terms to process in this run"
    )
    parser.add_argument(
        "--term",
        dest="term",
        help="Process a single ingredient term instead of pulling from the queue",
    )
    parser.add_argument(
        "--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    store = StateStore(load_settings().db_path)

    if args.term:
        process_terms([args.term])
        return

    pending = store.fetch_next_terms(limit=args.batch)
    process_terms(pending)


if __name__ == "__main__":
    main()
