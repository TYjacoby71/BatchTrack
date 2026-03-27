"""Batch list preference persistence service.

Synopsis:
Moves batch list preference reads/writes behind a service boundary so batch
routes avoid direct model/session persistence.

Glossary:
- Module boundary: Defines the ownership scope and responsibilities for this module.
"""

from __future__ import annotations

from app.extensions import db
from app.models import UserPreferences

BATCH_LIST_PREF_SCOPE = "batches_list"


class BatchPreferencesService:
    """Service helpers for batch list preference persistence."""

    @staticmethod
    def get_user_preferences(user_id: int):
        return UserPreferences.get_for_user(user_id)

    @staticmethod
    def load_scope_preferences(user_id: int) -> dict:
        prefs = BatchPreferencesService.get_user_preferences(user_id)
        return prefs.get_list_preferences(BATCH_LIST_PREF_SCOPE) if prefs else {}

    @staticmethod
    def persist_batch_list_preferences(
        *,
        user_id: int,
        visible_columns: list[str],
        filters: dict,
    ) -> bool:
        prefs = BatchPreferencesService.get_user_preferences(user_id)
        if not prefs:
            return False
        next_values = {
            "visible_columns": visible_columns,
            "status": filters.get("status") or "all",
            "recipe_id": filters.get("recipe_id"),
            "start": filters.get("start"),
            "end": filters.get("end"),
            "sort_by": filters.get("sort_by") or "date_desc",
        }
        previous_values = prefs.get_list_preferences(BATCH_LIST_PREF_SCOPE)
        if previous_values == next_values:
            return False
        prefs.set_list_preferences(BATCH_LIST_PREF_SCOPE, next_values, merge=False)
        db.session.commit()
        return True
