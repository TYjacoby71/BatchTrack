from __future__ import annotations

from pathlib import Path

"""
Centralized filesystem layout for the data_builder domain.

Goal: keep all paths consistent even as folders move around.
"""

ROOT_DIR = Path(__file__).resolve().parent

# Inputs / sources (CSV, vocab JSON, seed lists)
DATA_SOURCES_DIR = ROOT_DIR / "data_sources"
VOCAB_DIR = DATA_SOURCES_DIR / "vocab"
TERMS_FILE = DATA_SOURCES_DIR / "terms.json"

# Generated artifacts (JSON library, lookup files, normalized CSV)
OUTPUTS_DIR = ROOT_DIR / "outputs"
INGREDIENTS_OUTPUT_DIR = OUTPUTS_DIR / "ingredients"
TERM_STUBS_DIR = OUTPUTS_DIR / "term_stubs"
NORMALIZED_TERMS_CSV = OUTPUTS_DIR / "normalized_terms.csv"
PHYSICAL_FORMS_FILE = OUTPUTS_DIR / "physical_forms.json"
VARIATIONS_FILE = OUTPUTS_DIR / "variations.json"
TAXONOMIES_FILE = OUTPUTS_DIR / "taxonomies.json"

# State / compiler DB
DATABASE_DIR = ROOT_DIR / "database"
COMPILER_STATE_DB = DATABASE_DIR / "compiler_state.db"


def ensure_layout() -> None:
    DATA_SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    INGREDIENTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TERM_STUBS_DIR.mkdir(parents=True, exist_ok=True)

