"""Ingredient data builder package.

Note: keep imports lightweight so utility scripts (e.g. normalizers) can run
without requiring optional heavyweight dependencies (like the OpenAI SDK).
Import submodules directly as needed, e.g.:

    from data_builder.ingredients import database_manager
"""

__all__ = ["ai_worker", "compiler", "database_manager", "portal", "term_collector", "normalize_sources", "sources"]
