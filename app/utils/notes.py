"""Note helpers for timestamped entries.

Synopsis:
Formats and appends timestamped note entries for audit trails.

Glossary:
- Note entry: A single note with a saved timestamp prefix.
- Timestamp prefix: "[YYYY-MM-DD HH:MM:SS UTC]" header.
"""
from __future__ import annotations

import re
from datetime import datetime

from .timezone_utils import TimezoneUtils


_TIMESTAMP_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC\]")


# --- Format timestamp ---
# Purpose: Build a UTC timestamp string for notes.
def _format_timestamp(now: datetime | None = None) -> str:
    stamp = now or TimezoneUtils.utc_now()
    return stamp.strftime("%Y-%m-%d %H:%M:%S UTC")


# --- Append timestamped note ---
# Purpose: Append a timestamped note entry to existing notes.
def append_timestamped_note(existing: str | None, incoming: str | None) -> str:
    incoming_text = (incoming or "").strip()
    if not incoming_text:
        return existing or ""

    existing_text = (existing or "").strip()
    if existing_text and incoming_text == existing_text:
        return existing or existing_text

    if existing_text and incoming_text.startswith(existing_text):
        extra = incoming_text[len(existing_text):].strip()
        if not extra:
            return existing or existing_text
        incoming_text = extra

    if _TIMESTAMP_RE.match(incoming_text):
        entry = incoming_text
    else:
        entry = f"[{_format_timestamp()}] {incoming_text}"

    if not existing_text:
        return entry
    if existing_text.endswith(entry):
        return existing_text
    return f"{existing_text}\n\n{entry}"


__all__ = [
    "append_timestamped_note",
]
