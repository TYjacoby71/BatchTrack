"""Seed compiler_state.db vocab tables from data source JSON files.

This lets you ship curated vocab (forms/variations/categories/etc.) alongside the repo
and seed any environment (local, Replit, Render, production) deterministically.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from . import database_manager

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
VOCAB_DIR = BASE_DIR / "data_sources" / "vocab"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def seed_from_dir(vocab_dir: Path) -> None:
    database_manager.ensure_tables_exist()
    with database_manager.get_session() as session:
        # Ingredient categories (primary)
        for name in _read_json(vocab_dir / "ingredient_categories_primary.json"):
            if session.get(database_manager.IngredientCategoryTerm, name) is None:
                session.add(database_manager.IngredientCategoryTerm(name=name))

        # Master categories
        for name in _read_json(vocab_dir / "master_categories.json"):
            if session.get(database_manager.MasterCategoryTerm, name) is None:
                session.add(database_manager.MasterCategoryTerm(name=name))

        # Refinement levels
        for name in _read_json(vocab_dir / "refinement_levels.json"):
            if session.get(database_manager.RefinementLevelTerm, name) is None:
                session.add(database_manager.RefinementLevelTerm(name=name))

        # Physical forms
        for name in _read_json(vocab_dir / "physical_forms.json"):
            if session.get(database_manager.PhysicalFormTerm, name) is None:
                session.add(database_manager.PhysicalFormTerm(name=name))

        # Variations
        for name in _read_json(vocab_dir / "variations.json"):
            if session.get(database_manager.VariationTerm, name) is None:
                session.add(database_manager.VariationTerm(name=name, approved=True))

        # Master category rules
        rules = _read_json(vocab_dir / "master_category_rules.json")
        existing = {(r.master_category, r.source_type, r.source_value) for r in session.query(database_manager.MasterCategoryRule).all()}
        for r in rules:
            mc = (r.get("master_category") or "").strip()
            st = (r.get("source_type") or "").strip()
            sv = (r.get("source_value") or "").strip()
            if not mc or not st or not sv:
                continue
            key = (mc, st, sv)
            if key in existing:
                continue
            session.add(database_manager.MasterCategoryRule(master_category=mc, source_type=st, source_value=sv))
            existing.add(key)

    LOGGER.info("Seeded vocab tables from %s", vocab_dir)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    parser = argparse.ArgumentParser(description="Seed vocab tables from curated JSON files")
    parser.add_argument("--dir", default=str(VOCAB_DIR), help="Directory containing vocab JSON files")
    args = parser.parse_args(argv)

    vocab_dir = Path(args.dir).resolve()
    seed_from_dir(vocab_dir)


if __name__ == "__main__":
    main()

