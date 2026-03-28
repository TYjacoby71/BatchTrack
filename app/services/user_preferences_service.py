"""User preference orchestration helpers.

Synopsis:
Centralizes list-preference scope validation and persistence so route handlers
stay transport-focused while service code owns preference mutation rules.

Glossary:
- Scope: Namespaced key for a list/table preference payload.
- Merge mode: Update existing scope values by shallow-merging incoming keys.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from app.extensions import db
from app.models import UserPreferences

_SCOPE_RE = re.compile(r"[A-Za-z0-9:_-]{1,80}")


class UserPreferencesService:
    """Service boundary for list preference read/write flows."""

    @staticmethod
    def _scope_is_valid(scope: str | None) -> bool:
        return bool(_SCOPE_RE.fullmatch(scope or ""))

    @classmethod
    def get_list_preferences(
        cls, user_id: int, scope: str
    ) -> tuple[dict[str, Any], int]:
        """Fetch list preferences for a user/scope pair."""
        if not cls._scope_is_valid(scope):
            return {"success": False, "error": "Invalid preference scope"}, 400

        user_prefs = UserPreferences.get_for_user(user_id)
        if not user_prefs:
            return {"success": True, "scope": scope, "values": {}}, 200

        values = user_prefs.get_list_preferences(scope)
        return {"success": True, "scope": scope, "values": values}, 200

    @classmethod
    def update_list_preferences(
        cls,
        user_id: int,
        scope: str,
        payload: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], int]:
        """Persist list preferences for a user/scope pair."""
        if not cls._scope_is_valid(scope):
            return {"success": False, "error": "Invalid preference scope"}, 400

        data = payload or {}
        values = data.get("values")
        mode = str(data.get("mode", "merge") or "merge").lower()
        merge = mode != "replace"

        if values is None:
            # Backward-compatible payload shape: treat root object as values.
            values = data
            mode = "merge"
            merge = True

        if not isinstance(values, dict):
            return {
                "success": False,
                "error": "Preference values must be an object",
            }, 400

        user_prefs = UserPreferences.get_for_user(user_id)
        if not user_prefs:
            return {"success": False, "error": "Preferences unavailable"}, 400

        try:
            next_scope_values = user_prefs.set_list_preferences(
                scope, values, merge=merge
            )
            user_prefs.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            return {
                "success": True,
                "scope": scope,
                "values": next_scope_values,
                "mode": mode,
            }, 200
        except Exception:
            db.session.rollback()
            raise
