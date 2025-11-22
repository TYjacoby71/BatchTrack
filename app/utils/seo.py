from __future__ import annotations

import re
from urllib.parse import urljoin

from flask import current_app, has_request_context, request

__all__ = ["slugify_value", "absolute_url"]

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify_value(value: str, *, max_length: int | None = None, default: str = "item") -> str:
    """
    Convert arbitrary text to a URL-safe slug.

    Args:
        value: Source text.
        max_length: Optional length cap for the slug.
        default: Fallback value when the slug is empty after normalization.
    """
    if not value:
        return default

    slug = _NON_ALNUM.sub("-", value.lower().strip()).strip("-")
    if not slug:
        slug = default

    if max_length and max_length > 0:
        slug = slug[:max_length].rstrip("-")

    return slug or default


def absolute_url(path: str) -> str:
    """
    Build an absolute URL for the provided path.

    Prefers the active request context and falls back to ``EXTERNAL_BASE_URL``.
    """
    if not path:
        return ""

    if path.startswith(("http://", "https://")):
        return path

    if has_request_context():
        return urljoin(request.url_root, path.lstrip("/"))

    base = current_app.config.get("EXTERNAL_BASE_URL") if current_app else ""
    if base:
        return urljoin(base, path.lstrip("/"))

    return path
