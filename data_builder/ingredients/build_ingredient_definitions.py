#!/usr/bin/env python3
"""Create ingredient_definitions table and link compiled clusters."""
from __future__ import annotations

import argparse

from . import database_manager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize ingredient_definitions and link clusters.")
    parser.add_argument(
        "--db-path",
        default="",
        help="Path to Final DB.db (defaults to FINAL_DB_PATH or output/Final DB.db).",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.db_path:
        database_manager.configure_db_path(args.db_path)

    database_manager.ensure_tables_exist()

    with database_manager.get_session() as session:
        total_defs = session.query(database_manager.IngredientDefinition).count()
        total_clusters = session.query(database_manager.CompiledClusterRecord).count()
        linked_clusters = (
            session.query(database_manager.CompiledClusterRecord)
            .filter(database_manager.CompiledClusterRecord.definition_id.isnot(None))
            .count()
        )

    print("ingredient_definitions initialized.")
    print(f"Definitions: {total_defs}")
    print(f"Clusters: {total_clusters}")
    print(f"Clusters linked to definitions: {linked_clusters}")


if __name__ == "__main__":
    main()
