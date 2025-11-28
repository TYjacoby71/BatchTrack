"""Configuration helpers for the ingredient library builder."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class Settings:
    """Runtime configuration sourced from environment variables."""

    project_root: Path
    db_path: Path
    output_dir: Path
    terms_path: Path
    llm_model: str
    temperature: float
    max_retries: int
    dry_run: bool

    @property
    def vocab_path(self) -> Path:
        return self.project_root / "data_builder" / "taxonomy"  # reserved for future assets


DEFAULT_PHYSICAL_FORMS: List[str] = [
    "Powder",
    "Liquid",
    "Whole",
    "Cut & Sifted",
    "Granules",
    "Flakes",
    "Paste",
    "Crystal",
    "Oil",
    "Butter",
    "Resin",
]

DEFAULT_INGREDIENT_CATEGORY_TAGS: List[str] = [
    "Actives",
    "Botanicals > Herbs",
    "Botanicals > Spices",
    "Botanicals > Flowers",
    "Botanicals > Extracts",
    "Clays & Muds",
    "Chemicals",
    "Oils & Butters",
    "Surfactants",
    "Waxes",
]


def load_settings() -> Settings:
    root = Path(__file__).resolve().parent.parent
    db_path = Path(os.getenv("DATA_BUILDER_DB", root / "data_builder" / "state.db"))
    output_dir = Path(os.getenv("DATA_BUILDER_OUTPUT", root / "data_builder" / "output"))
    terms_path = Path(os.getenv("DATA_BUILDER_TERMS", root / "data_builder" / "terms.txt"))

    return Settings(
        project_root=root,
        db_path=db_path,
        output_dir=output_dir,
        terms_path=terms_path,
        llm_model=os.getenv("DATA_BUILDER_MODEL", "gpt-4.1-mini"),
        temperature=float(os.getenv("DATA_BUILDER_TEMPERATURE", "0.2")),
        max_retries=int(os.getenv("DATA_BUILDER_MAX_RETRIES", "3")),
        dry_run=os.getenv("DATA_BUILDER_DRY_RUN", "false").lower() == "true",
    )


__all__ = [
    "Settings",
    "load_settings",
    "DEFAULT_PHYSICAL_FORMS",
    "DEFAULT_INGREDIENT_CATEGORY_TAGS",
]
