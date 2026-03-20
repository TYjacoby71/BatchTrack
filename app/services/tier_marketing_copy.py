"""Tier marketing copy parsing/render helpers.

Synopsis:
Normalize optional tier marketing fields into stable card copy payloads for
signup/pricing surfaces while preserving backward compatibility with legacy
description text.

Glossary:
- Legacy description: Existing freeform `SubscriptionTier.description` value.
- Marketing bullets: Optional newline list that drives structured card lists.
"""

from __future__ import annotations

import re
from typing import Any

from markupsafe import Markup, escape

_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")
_STAR_SPLIT_RE = re.compile(r"\s+\*(?=\S)")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC_RE = re.compile(
    r"(?<!\*)\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)|(?<!_)_(?!\s)([^_]+?)(?<!\s)_(?!_)"
)
_CODE_RE = re.compile(r"`([^`]+)`")

_MAX_SUMMARY_CHARS = 200
_MAX_BULLETS = 100


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_line_breaks(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _truncate_summary(value: str, *, max_chars: int = _MAX_SUMMARY_CHARS) -> str:
    cleaned = " ".join(_clean_text(value).split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"


def _normalize_bullet_line(line: str) -> str:
    without_prefix = _BULLET_PREFIX_RE.sub("", _clean_text(line))
    return " ".join(without_prefix.split())


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw_value in values:
        value = _clean_text(raw_value)
        if not value:
            continue
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
    return deduped


def parse_marketing_bullets(
    raw_bullets: Any, *, max_items: int | None = _MAX_BULLETS
) -> list[str]:
    """Return cleaned marketing bullets from newline-delimited text."""
    if isinstance(raw_bullets, (list, tuple, set)):
        parsed_items = [_normalize_bullet_line(str(item or "")) for item in raw_bullets]
        parsed_items = _dedupe_preserve_order(parsed_items)
        return parsed_items[:max_items] if isinstance(max_items, int) else parsed_items

    text_value = _clean_text(raw_bullets)
    if not text_value:
        return []

    lines = _normalize_line_breaks(text_value).split("\n")
    parsed = [_normalize_bullet_line(line) for line in lines]
    parsed = _dedupe_preserve_order(parsed)
    return parsed[:max_items] if isinstance(max_items, int) else parsed


def _parse_legacy_bullets(description: str) -> tuple[str, list[str]]:
    """Derive a summary and bullets from legacy freeform description text."""
    normalized = _clean_text(description)
    if not normalized:
        return ("", [])

    summary = ""
    bullets: list[str] = []

    multiline_lines = [
        _clean_text(line) for line in _normalize_line_breaks(description).split("\n")
    ]
    multiline_lines = [line for line in multiline_lines if line]
    explicit_multiline_bullets = [
        _normalize_bullet_line(line)
        for line in multiline_lines
        if _BULLET_PREFIX_RE.match(line)
    ]
    if explicit_multiline_bullets:
        non_bullet_lines = [
            line for line in multiline_lines if not _BULLET_PREFIX_RE.match(line)
        ]
        summary = _truncate_summary(non_bullet_lines[0] if non_bullet_lines else "")
        bullets = explicit_multiline_bullets

    if not bullets:
        star_chunks = [
            _normalize_bullet_line(chunk)
            for chunk in _STAR_SPLIT_RE.split(" ".join(normalized.split()))
            if _clean_text(chunk)
        ]
        if len(star_chunks) >= 2:
            summary = _truncate_summary(star_chunks[0])
            bullets = star_chunks[1:]

    if not bullets:
        sentence_chunks = [
            _clean_text(chunk)
            for chunk in _SENTENCE_SPLIT_RE.split(" ".join(normalized.split()))
            if _clean_text(chunk)
        ]
        if sentence_chunks:
            summary = _truncate_summary(sentence_chunks[0])
            bullets = sentence_chunks[1:]

    if not summary:
        summary = _truncate_summary(normalized)

    bullets = _dedupe_preserve_order([_normalize_bullet_line(item) for item in bullets])
    summary_key = summary.casefold()
    filtered_bullets = [item for item in bullets if item.casefold() != summary_key]
    return (summary, filtered_bullets[:_MAX_BULLETS])


def render_inline_marketing(value: Any) -> Markup:
    """Render a safe subset of inline markdown syntax."""
    text_value = _clean_text(value)
    if not text_value:
        return Markup("")

    rendered = str(escape(text_value))
    rendered = _CODE_RE.sub(
        lambda match: f"<code>{match.group(1) or ''}</code>",
        rendered,
    )
    rendered = _BOLD_RE.sub(
        lambda match: f"<strong>{match.group(1) or match.group(2) or ''}</strong>",
        rendered,
    )
    rendered = _ITALIC_RE.sub(
        lambda match: f"<em>{match.group(1) or match.group(2) or ''}</em>",
        rendered,
    )
    return Markup(rendered)


def build_marketing_copy(
    *,
    marketing_tagline: Any,
    marketing_summary: Any,
    marketing_bullets: Any,
    legacy_description: Any,
    default_tagline: str = "Built for makers",
) -> dict[str, Any]:
    """Return normalized marketing copy with safe rich-text variants."""
    tagline = _clean_text(marketing_tagline)
    summary = _clean_text(marketing_summary)
    bullets = parse_marketing_bullets(marketing_bullets)
    legacy_description_text = _clean_text(legacy_description)

    if not summary or not bullets:
        fallback_summary, fallback_bullets = _parse_legacy_bullets(
            legacy_description_text
        )
        if not summary:
            summary = fallback_summary
        if not bullets:
            bullets = fallback_bullets

    if not tagline:
        tagline = summary or default_tagline

    bullets = _dedupe_preserve_order(bullets)[:_MAX_BULLETS]

    return {
        "tagline": tagline or default_tagline,
        "summary": summary,
        "bullets": bullets,
        "summary_html": render_inline_marketing(summary),
        "bullets_html": [render_inline_marketing(item) for item in bullets],
        "uses_legacy_description": bool(
            legacy_description_text
            and (
                not _clean_text(marketing_summary)
                or not parse_marketing_bullets(marketing_bullets)
            )
        ),
    }
