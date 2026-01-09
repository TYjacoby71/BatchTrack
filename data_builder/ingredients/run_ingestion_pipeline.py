"""One-shot deterministic ingestion pipeline (no knobs).

This module is the canonical entrypoint for the *deterministic* ingredient ingestion system.

It:
- ingests CosIng + TGSC rows into `source_items`
- builds a merged identity catalog in `source_catalog_items`
- derives deterministic tags/specs/display names
- de-duplicates into `merged_item_forms`
- bundles items into `source_definitions` (definition clusters)
- writes initial `normalized_terms` from source ingest, then adds more canonical
  terms from the merged catalog (deterministic clustering)

Notes:
- The database path is controlled via `COMPILER_DB_PATH` (defaults to compiler_state.db).
- The pipeline does **not** write CSV exports automatically (to avoid huge generated files).
- If you want a CSV export, run `derive_terms_from_catalog.py --csv-out ...` explicitly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from . import (
    bundle_source_items,
    database_manager,
    derive_source_item_display_names,
    derive_source_item_specs,
    derive_source_item_tags,
    derive_source_item_variation_bypass,
    derive_terms_from_catalog,
    enqueue_normalized,
    ingest_source_items,
    merge_source_catalog,
    merge_source_items,
    split_botanical_parts,
)

LOGGER = logging.getLogger(__name__)


def _reset_ingestion_tables() -> None:
    """Clear ingestion-stage tables for a clean one-shot run."""
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        # Compiler/AI stages (clear for a truly clean one-time run)
        session.query(database_manager.TaskQueue).delete()
        session.query(database_manager.IngredientItemValue).delete()
        session.query(database_manager.IngredientItemRecord).delete()
        session.query(database_manager.IngredientMasterCategory).delete()
        session.query(database_manager.IngredientRecord).delete()

        # Raw ingestion + derived staging
        session.query(database_manager.SourceItem).delete()
        session.query(database_manager.SourceCatalogItem).delete()
        session.query(database_manager.MergedItemForm).delete()
        session.query(database_manager.SourceDefinition).delete()
        # Canonical terms (compiler input)
        session.query(database_manager.NormalizedTerm).delete()
        # Optional: source_terms cursor table (safe to rebuild)
        session.query(database_manager.SourceTerm).delete()

        # PubChem deterministic enrichment cache/matches
        session.query(database_manager.PubChemItemMatch).delete()
        session.query(database_manager.PubChemTermMatch).delete()
        session.query(database_manager.PubChemCompound).delete()


def run() -> None:
    """Run the canonical deterministic ingestion pipeline."""
    database_manager.ensure_tables_exist()
    LOGGER.info("Using state DB: %s", database_manager.DB_PATH)

    # Canonical input files (bundled in-repo).
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data_sources"
    cosing_path = data_dir / "cosing.csv"
    tgsc_path = data_dir / "tgsc_ingredients.csv"

    if not cosing_path.exists():
        raise FileNotFoundError(f"Missing CosIng CSV at {cosing_path}")
    if not tgsc_path.exists():
        raise FileNotFoundError(f"Missing TGSC CSV at {tgsc_path}")

    # One-shot run: wipe the ingestion-stage tables to guarantee non-overlap.
    _reset_ingestion_tables()

    # 1) Ingest per-row items (variation/form parsing + provenance) + seed normalized_terms.
    inserted_items, inserted_terms = ingest_source_items.ingest_sources(
        cosing_path=cosing_path,
        tgsc_path=tgsc_path,
        limit=None,
        sample_size=None,
        seed=None,
        include=[],
        write_terms=True,
    )
    LOGGER.info("source_items ingested: inserted=%s", inserted_items)
    LOGGER.info("normalized_terms seeded from sources: inserted=%s", inserted_terms)

    # 2) Merge catalog identities (CAS/EC/INCI) for cross-source enrichment.
    merge_stats = merge_source_catalog.build_catalog(
        cosing_path=cosing_path,
        tgsc_path=tgsc_path,
        limit=None,
        include=None,
    )
    LOGGER.info("catalog merged: %s", merge_stats)

    # 3) Deterministic post-passes on source_items.
    LOGGER.info("deriving source item display names...")
    LOGGER.info("display names: %s", derive_source_item_display_names.derive_display_names(limit=0))
    LOGGER.info("deriving source item tags...")
    LOGGER.info("tags: %s", derive_source_item_tags.derive_tags(limit=0))
    LOGGER.info("deriving source item specs...")
    LOGGER.info("specs: %s", derive_source_item_specs.derive_specs(limit=0))
    LOGGER.info("deriving source item variation_bypass flags...")
    LOGGER.info("variation_bypass: %s", derive_source_item_variation_bypass.derive_variation_bypass(limit=0))

    # 4) Merge duplicate item-forms.
    LOGGER.info("merging duplicate item-forms...")
    LOGGER.info("merged item forms: %s", merge_source_items.merge_source_items(limit=0))

    # 4b) Botanical part split (binomial plant-derived only; deterministic).
    LOGGER.info("splitting botanical parts into part-level terms/items...")
    LOGGER.info("botanical part split: %s", split_botanical_parts.split_botanical_parts(limit_terms=0))

    # 5) Bundle source_items into definition clusters.
    LOGGER.info("bundling source_items into source_definitions...")
    LOGGER.info("bundles: %s", bundle_source_items.bundle(limit=0))

    # 6) Derive additional canonical normalized_terms from the merged catalog.
    # This step may insert new terms beyond the source-ingest seeded set.
    LOGGER.info("deriving canonical normalized_terms from merged catalog...")
    stats = derive_terms_from_catalog.build_terms_from_catalog(
        csv_out=None,
        limit=None,
        include=[],
        no_db=False,
    )
    LOGGER.info("normalized_terms: %s", stats)

    # 7) Seed compiler queue from normalized_terms (DB->DB). This is the bridge into the AI compiler.
    inserted_queue = enqueue_normalized._seed_from_db(limit=None)  # intentionally one-way, no CSV
    LOGGER.info("task_queue seeded from normalized_terms: inserted=%s", inserted_queue)


def main() -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    run()


if __name__ == "__main__":
    main()
