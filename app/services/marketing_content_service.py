"""DB-first persistence helpers for public marketing content and waitlists.

Synopsis:
Provides a durable storage layer for homepage marketing content and legacy
waitlist rows by storing payloads in app settings first, with JSON files kept
as a compatibility mirror for existing tooling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.utils.json_store import read_json_file, write_json_file
from app.utils.settings import get_settings, save_settings

logger = logging.getLogger(__name__)


class MarketingContentService:
    """DB-first marketing content persistence."""

    REVIEWS_KEY = "marketing_reviews"
    SPOTLIGHTS_KEY = "marketing_spotlights"
    WAITLIST_ENTRIES_KEY = "marketing_waitlist_entries"

    REVIEWS_PATH = "data/reviews.json"
    SPOTLIGHTS_PATH = "data/spotlights.json"
    WAITLIST_PATH = "data/waitlist.json"

    @staticmethod
    def _safe_list(value: Any) -> List[Any]:
        return list(value) if isinstance(value, list) else []

    @classmethod
    def get_reviews(cls) -> List[Dict[str, Any]]:
        settings = get_settings()
        reviews = settings.get(cls.REVIEWS_KEY)
        if isinstance(reviews, list):
            return reviews
        return cls._safe_list(read_json_file(cls.REVIEWS_PATH, default=[]))

    @classmethod
    def save_reviews(cls, reviews: List[Dict[str, Any]]) -> None:
        normalized = cls._safe_list(reviews)
        settings = get_settings()
        settings[cls.REVIEWS_KEY] = normalized
        if not save_settings(settings):
            logger.warning("Failed to persist marketing reviews to DB settings")
        write_json_file(cls.REVIEWS_PATH, normalized)

    @classmethod
    def get_spotlights(cls) -> List[Dict[str, Any]]:
        settings = get_settings()
        spotlights = settings.get(cls.SPOTLIGHTS_KEY)
        if isinstance(spotlights, list):
            return spotlights
        return cls._safe_list(read_json_file(cls.SPOTLIGHTS_PATH, default=[]))

    @classmethod
    def save_spotlights(cls, spotlights: List[Dict[str, Any]]) -> None:
        normalized = cls._safe_list(spotlights)
        settings = get_settings()
        settings[cls.SPOTLIGHTS_KEY] = normalized
        if not save_settings(settings):
            logger.warning("Failed to persist marketing spotlights to DB settings")
        write_json_file(cls.SPOTLIGHTS_PATH, normalized)

    @classmethod
    def get_waitlist_entries(cls) -> List[Dict[str, Any]]:
        settings = get_settings()
        waitlist_entries = settings.get(cls.WAITLIST_ENTRIES_KEY)
        if isinstance(waitlist_entries, list):
            return waitlist_entries
        return cls._safe_list(read_json_file(cls.WAITLIST_PATH, default=[]))

    @classmethod
    def has_waitlist_entry(cls, email: str, waitlist_key: str) -> bool:
        normalized_email = (email or "").strip().lower()
        normalized_waitlist_key = (waitlist_key or "").strip().lower()
        if not normalized_email:
            return False
        return any(
            isinstance(entry, dict)
            and (entry.get("email") or "").strip().lower() == normalized_email
            and (
                (entry.get("waitlist_key") or entry.get("source") or "").strip().lower()
                == normalized_waitlist_key
            )
            for entry in cls.get_waitlist_entries()
        )

    @classmethod
    def append_waitlist_entry(cls, entry: Dict[str, Any]) -> bool:
        if not isinstance(entry, dict):
            return False

        email = (entry.get("email") or "").strip().lower()
        waitlist_key = (
            (entry.get("waitlist_key") or entry.get("source") or "").strip().lower()
        )
        if email and waitlist_key and cls.has_waitlist_entry(email, waitlist_key):
            return False

        entries = cls.get_waitlist_entries()
        entries.append(entry)

        settings = get_settings()
        settings[cls.WAITLIST_ENTRIES_KEY] = entries
        if not save_settings(settings):
            logger.warning("Failed to persist waitlist entries to DB settings")
        write_json_file(cls.WAITLIST_PATH, entries)
        return True
