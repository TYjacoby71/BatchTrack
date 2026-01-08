"""One-shot deterministic ingestion pipeline (canonical, no overlap).

This is the single entrypoint for the deterministic ingestion flow.

It populates (pre-AI):
- source_catalog_items (CosIng + TGSC identity merge)
- source_items (row-level items + parsed term/variation/form + deterministic enrichments)
- merged_item_forms (deduped item-forms)
- source_definitions (definition clusters/bundles)
- normalized_terms (compiler base-term list)
- term_seed_item_forms (canonical item seeds for each term; used by PubChem + compiler)
- task_queue (seeded from normalized_terms; compiler input)

Notes:
- Uses COMPILER_DB_PATH to choose the SQLite state DB (defaults to compiler_state.db).
- Does NOT write output/normalized_terms.csv by default (set COMPILER_WRITE_NORMALIZED_CSV=1 to export).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from . import (
    bundle_source_items,
    database_manager,
    derive_source_item_display_names,
    derive_source_item_specs,
    derive_source_item_tags,
    derive_source_item_variation_bypass,
    derive_terms_from_catalog,
    ingest_source_items,
    merge_source_catalog,
    merge_source_items,
)
from .build_term_seed_item_forms import build_term_seed_item_forms

LOGGER = logging.getLogger(__name__)


def _reset_tables() -> None:
    """Clear ingestion-stage tables for a clean deterministic run."""
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        # Deterministic ingestion products
        session.query(database_manager.SourceItem).delete()
        session.query(database_manager.SourceCatalogItem).delete()
        session.query(database_manager.MergedItemForm).delete()
        session.query(database_manager.SourceDefinition).delete()
        session.query(database_manager.NormalizedTerm).delete()
        session.query(database_manager.SourceTerm).delete()
        session.query(database_manager.TermSeedItemForm).delete()

        # PubChem caches/matches (pre-AI enrichment)
        session.query(database_manager.PubChemItemMatch).delete()
        session.query(database_manager.PubChemCompound).delete()

        # Compiler queue + outputs (AI stage) - keep empty on fresh ingest
        session.query(database_manager.TaskQueue).delete()
        session.query(database_manager.IngredientItemValue).delete()
        session.query(database_manager.IngredientItemRecord).delete()
        session.query(database_manager.IngredientMasterCategory).delete()
        session.query(database_manager.IngredientRecord).delete()


def run() -> None:
    database_manager.ensure_tables_exist()
    LOGGER.info("Using state DB: %s", database_manager.DB_PATH)

    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data_sources"
    cosing_path = data_dir / "cosing.csv"
    tgsc_path = data_dir / "tgsc_ingredients.csv"
    if not cosing_path.exists():
        raise FileNotFoundError(f"Missing CosIng CSV at {cosing_path}")
    if not tgsc_path.exists():
        raise FileNotFoundError(f"Missing TGSC CSV at {tgsc_path}")

    _reset_tables()

    # 1) Merge identity catalog
    stats = merge_source_catalog.build_catalog(cosing_path=cosing_path, tgsc_path=tgsc_path, limit=None, include=None)
    LOGGER.info("catalog merged: %s", stats)

    # 2) Ingest items (row-level)
    inserted_items, inserted_terms = ingest_source_items.ingest_sources(
        cosing_path=cosing_path,
        tgsc_path=tgsc_path,
        limit=None,
        sample_size=None,
        seed=None,
        include=[],
        write_terms=True,
    )
    LOGGER.info("source_items ingested: inserted=%s, normalized_terms_inserted=%s", inserted_items, inserted_terms)

    # 3) Deterministic post-passes
    LOGGER.info("display names: %s", derive_source_item_display_names.derive_display_names(limit=0))
    LOGGER.info("tags: %s", derive_source_item_tags.derive_tags(limit=0))
    LOGGER.info("specs: %s", derive_source_item_specs.derive_specs(limit=0))
    LOGGER.info("variation_bypass: %s", derive_source_item_variation_bypass.derive_variation_bypass(limit=0))

    # 4) Merge duplicate item-forms
    LOGGER.info("merged item forms: %s", merge_source_items.merge_source_items(limit=0))

    # 5) Bundle items into definition clusters
    LOGGER.info("bundles: %s", bundle_source_items.bundle(limit=0))

    # 6) Derive additional canonical terms from merged catalog (DB is source-of-truth)
    write_csv = os.getenv("COMPILER_WRITE_NORMALIZED_CSV", "0").strip().lower() in {"1", "true", "yes", "on"}
    csv_out = (base_dir / "output" / "normalized_terms.csv") if write_csv else None
    tstats = derive_terms_from_catalog.build_terms_from_catalog(csv_out=csv_out, limit=None, include=[], no_db=False)
    LOGGER.info("terms from catalog: %s", tstats)

    # 7) Build canonical term seed items from merged item-forms
    LOGGER.info("term_seed_item_forms: %s", build_term_seed_item_forms())

    # 8) Seed compiler queue from normalized_terms (DB → DB)
    from .enqueue_normalized import _seed_from_db  # local import to reuse existing helper

    inserted = _seed_from_db(limit=None)
    LOGGER.info("seeded task_queue from normalized_terms: inserted=%s", inserted)


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    run()


if __name__ == "__main__":
    main()

