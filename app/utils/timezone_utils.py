from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from typing import Dict, List, Set, Tuple

import pytz
from flask import has_request_context
from flask_login import current_user

DEFAULT_TIMEZONE = "UTC"
SUGGESTED_SECTION_LABEL = "Suggested"
_PRIORITY_TIMEZONES = (
    "US/Eastern",
    "US/Central",
    "US/Mountain",
    "US/Pacific",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Australia/Sydney",
)

_REGION_SEQUENCE = (
    "North America",
    "Europe",
    "Asia",
    "Australia/Pacific",
    "Africa",
    "South America",
    "Other",
)

_SOUTH_AMERICA_PREFIXES = (
    "America/Argentina",
    "America/Asuncion",
    "America/Bogota",
    "America/Caracas",
    "America/La_Paz",
    "America/Lima",
    "America/Montevideo",
    "America/Santiago",
    "America/Sao_Paulo",
)

_TIMEZONE_ALIASES: Dict[str, str] = {
    "US/Eastern": "Eastern Time (US)",
    "US/Central": "Central Time (US)",
    "US/Mountain": "Mountain Time (US)",
    "US/Pacific": "Pacific Time (US)",
    "US/Alaska": "Alaska Time (US)",
    "US/Hawaii": "Hawaii Time (US)",
    "Europe/London": "Greenwich Mean Time",
    "Europe/Paris": "Central European Time",
    "Europe/Berlin": "Central European Time",
    "Europe/Rome": "Central European Time",
    "Europe/Madrid": "Central European Time",
    "Europe/Amsterdam": "Central European Time",
    "Asia/Tokyo": "Japan Standard Time",
    "Asia/Shanghai": "China Standard Time",
    "Asia/Kolkata": "India Standard Time",
    "Asia/Dubai": "Gulf Standard Time",
    "Australia/Sydney": "Australian Eastern Time",
    "Australia/Melbourne": "Australian Eastern Time",
    "Australia/Perth": "Australian Western Time",
    "Canada/Eastern": "Eastern Time (Canada)",
    "Canada/Central": "Central Time (Canada)",
    "Canada/Mountain": "Mountain Time (Canada)",
    "Canada/Pacific": "Pacific Time (Canada)",
}


class TimezoneUtils:
    """Utilities for consistent timezone handling across the application."""

    TIMEZONE_ALIASES = _TIMEZONE_ALIASES
    PRIORITY_TIMEZONES = _PRIORITY_TIMEZONES

    @staticmethod
    def get_available_timezones() -> List[str]:
        """Return every timezone identifier known to pytz."""
        return list(pytz.all_timezones)

    @staticmethod
    def get_common_timezones() -> List[str]:
        """Return the common subset of pytz timezones."""
        return list(pytz.common_timezones)

    @staticmethod
    def get_grouped_timezones(
        detected_timezone: str | None = None,
    ) -> Dict[str, List[Tuple[str, str]]]:
        """
        Return timezones grouped by region, optionally highlighting a detected zone.
        """
        grouped: Dict[str, List[Tuple[str, str]]] = {}
        seen: Set[str] = set()

        suggestions = TimezoneUtils._build_suggestions(detected_timezone, seen)
        if suggestions:
            grouped[SUGGESTED_SECTION_LABEL] = suggestions

        for region in _REGION_SEQUENCE:
            grouped.setdefault(region, [])

        for tz_name in TimezoneUtils.PRIORITY_TIMEZONES:
            TimezoneUtils._append_timezone(grouped, tz_name, seen)

        for tz_name in sorted(pytz.all_timezones):
            TimezoneUtils._append_timezone(grouped, tz_name, seen)

        return {region: items for region, items in grouped.items() if items}

    @staticmethod
    def _append_timezone(
        grouped: Dict[str, List[Tuple[str, str]]],
        tz_name: str,
        seen: Set[str],
    ) -> None:
        if tz_name in seen or not TimezoneUtils.validate_timezone(tz_name):
            return

        region = TimezoneUtils._get_timezone_region(tz_name)
        grouped.setdefault(region, [])
        grouped[region].append((tz_name, TimezoneUtils._format_timezone_display(tz_name)))
        seen.add(tz_name)

    @staticmethod
    def _build_suggestions(
        detected_timezone: str | None, seen: Set[str]
    ) -> List[Tuple[str, str]]:
        if not detected_timezone or not TimezoneUtils.validate_timezone(detected_timezone):
            return []

        suggestions: List[Tuple[str, str]] = [
            (
                detected_timezone,
                f"{TimezoneUtils._format_timezone_display(detected_timezone)} (detected)",
            )
        ]
        seen.add(detected_timezone)

        region = TimezoneUtils._get_timezone_region(detected_timezone)
        for tz_name in sorted(pytz.all_timezones):
            if tz_name in seen:
                continue
            if TimezoneUtils._get_timezone_region(tz_name) != region:
                continue
            suggestions.append((tz_name, TimezoneUtils._format_timezone_display(tz_name)))
            seen.add(tz_name)
            if len(suggestions) >= 5:  # detected + 4 related entries
                break

        return suggestions

    @staticmethod
    def _get_timezone_region(tz_name: str) -> str:
        prefix = tz_name.split("/", 1)[0]
        if prefix in {"US", "Canada"}:
            return "North America"
        if prefix == "America":
            return "South America" if tz_name.startswith(_SOUTH_AMERICA_PREFIXES) else "North America"
        if prefix == "Europe":
            return "Europe"
        if prefix == "Asia":
            return "Asia"
        if prefix in {"Australia", "Pacific"}:
            return "Australia/Pacific"
        if prefix == "Africa":
            return "Africa"
        return "Other"

    @staticmethod
    def _format_timezone_display(tz_name: str) -> str:
        alias = TimezoneUtils.TIMEZONE_ALIASES.get(tz_name)
        if alias:
            return alias

        parts = tz_name.split("/")
        if len(parts) >= 2:
            city = parts[-1].replace("_", " ")
            region = parts[0].replace("_", " ")
            return f"{city} ({region})"

        return tz_name.replace("_", " ")

    @staticmethod
    def format_timezone_display(tz_name: str) -> str:
        """Expose display formatting for templates."""
        return TimezoneUtils._format_timezone_display(tz_name)

    @staticmethod
    def validate_timezone(tz_name: str | None) -> bool:
        """Return True when the timezone string exists in pytz."""
        return bool(tz_name) and tz_name in pytz.all_timezones_set

    @staticmethod
    def _get_timezone(tz_name: str):
        if not TimezoneUtils.validate_timezone(tz_name):
            raise ValueError(f"Invalid timezone: {tz_name}")
        return pytz.timezone(tz_name)

    @staticmethod
    def convert_time(dt: datetime, from_tz: str, to_tz: str) -> datetime:
        """Convert a datetime from one explicit timezone to another."""
        source = TimezoneUtils._get_timezone(from_tz)
        target = TimezoneUtils._get_timezone(to_tz)
        localized = source.localize(dt) if dt.tzinfo is None else dt.astimezone(source)
        return localized.astimezone(target)

    @staticmethod
    def convert_to_timezone(
        dt: datetime | None, to_timezone: str, assume_utc: bool = True
    ) -> datetime | None:
        """Convert a datetime into the target timezone, assuming UTC for naive values."""
        if dt is None:
            return None
        target = TimezoneUtils._get_timezone(to_timezone if TimezoneUtils.validate_timezone(to_timezone) else DEFAULT_TIMEZONE)
        aware = TimezoneUtils.ensure_timezone_aware(dt, assume_utc=assume_utc)
        return aware.astimezone(target)

    @staticmethod
    def get_user_timezone_display(user_timezone: str | None) -> str:
        """Return a human-friendly timezone label, falling back to the default."""
        if not user_timezone or not TimezoneUtils.validate_timezone(user_timezone):
            return f"{DEFAULT_TIMEZONE} (Default)"
        return TimezoneUtils._format_timezone_display(user_timezone)

    @staticmethod
    def get_utc_offset(tz_name: str) -> str:
        """Return the UTC offset string for the provided timezone."""
        if not TimezoneUtils.validate_timezone(tz_name):
            return "+00:00"
        tz = TimezoneUtils._get_timezone(tz_name)
        offset = datetime.now(tz).strftime("%z")
        return f"{offset[:3]}:{offset[3:]}" if len(offset) == 5 else "+00:00"

    @staticmethod
    def utc_now() -> datetime:
        """Return the current UTC timestamp (timezone aware)."""
        return datetime.now(dt_timezone.utc)

    @staticmethod
    def now() -> datetime:
        """Return the current time localized for the active user."""
        localized = TimezoneUtils.to_user_timezone(TimezoneUtils.utc_now())
        return localized if localized is not None else TimezoneUtils.utc_now()

    @staticmethod
    def get_user_timezone() -> str:
        """Return the timezone configured for the authenticated user."""
        return TimezoneUtils._current_user_timezone()

    @staticmethod
    def _current_user_timezone() -> str:
        if not has_request_context():
            return DEFAULT_TIMEZONE
        try:
            user = current_user
        except Exception:
            return DEFAULT_TIMEZONE
        if user and getattr(user, "is_authenticated", False):
            candidate = getattr(user, "timezone", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
            if TimezoneUtils.validate_timezone(candidate):
                return candidate
        return DEFAULT_TIMEZONE

    @staticmethod
    def _resolve_user_timezone(user_timezone: str | None = None) -> str:
        if user_timezone and TimezoneUtils.validate_timezone(user_timezone):
            return user_timezone
        return TimezoneUtils._current_user_timezone()

    @staticmethod
    def to_user_timezone(
        dt: datetime | None, user_timezone: str | None = None
    ) -> datetime | None:
        """Convert a datetime into the user's timezone for display."""
        if dt is None:
            return None
        target_name = TimezoneUtils._resolve_user_timezone(user_timezone)
        target = TimezoneUtils._get_timezone(target_name)
        aware = TimezoneUtils.ensure_timezone_aware(dt)
        return aware.astimezone(target)

    @staticmethod
    def from_user_timezone(
        dt: datetime | None, user_timezone: str | None = None
    ) -> datetime | None:
        """Convert a user-supplied datetime into UTC for storage."""
        if dt is None:
            return None
        source_name = TimezoneUtils._resolve_user_timezone(user_timezone)
        source = TimezoneUtils._get_timezone(source_name)
        localized = source.localize(dt) if dt.tzinfo is None else dt.astimezone(source)
        return localized.astimezone(dt_timezone.utc)

    @staticmethod
    def format_for_user(
        dt: datetime | None, format_string: str = "%Y-%m-%d %H:%M:%S", user_timezone: str | None = None
    ) -> str:
        """Format a datetime for presentation in the user's timezone."""
        localized = TimezoneUtils.to_user_timezone(dt, user_timezone)
        return localized.strftime(format_string) if localized else ""

    @staticmethod
    def ensure_timezone_aware(
        dt: datetime | None, assume_utc: bool = True
    ) -> datetime | None:
        """Guarantee that a datetime carries timezone information."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            if not assume_utc:
                raise ValueError("Naive datetime provided without explicit timezone handling.")
            return dt.replace(tzinfo=dt_timezone.utc)
        return dt

    @staticmethod
    def safe_datetime_compare(
        dt1: datetime | None, dt2: datetime | None, assume_utc: bool = True
    ) -> bool:
        """Return True when dt1 is later than dt2, handling naive inputs safely."""
        if dt1 is None or dt2 is None:
            return False
        first = TimezoneUtils.ensure_timezone_aware(dt1, assume_utc)
        second = TimezoneUtils.ensure_timezone_aware(dt2, assume_utc)
        return bool(first and second and first > second)

    @staticmethod
    def format_datetime_for_api(
        dt: datetime | None, user_timezone: str | None = None
    ) -> Dict[str, str | None]:
        """Produce a structured payload containing UTC and localized timestamps."""
        if dt is None:
            return {"utc": None, "local": None, "display": None, "timezone": None}

        aware = TimezoneUtils.ensure_timezone_aware(dt)
        if aware is None:
            return {"utc": None, "local": None, "display": None, "timezone": None}

        target_name = TimezoneUtils._resolve_user_timezone(user_timezone)
        localized = TimezoneUtils.to_user_timezone(aware, target_name)

        return {
            "utc": aware.isoformat(),
            "local": localized.isoformat() if localized else None,
            "display": localized.strftime("%b %d, %Y %I:%M %p %Z") if localized else None,
            "timezone": target_name,
        }