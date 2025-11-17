import re
from urllib.parse import urljoin

from flask import request, current_app


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify_value(value: str) -> str:
    """Convert a string into a URL-friendly slug without external deps."""
    if not value:
        return ""
    value = value.lower().strip()
    value = _NON_ALNUM.sub("-", value)
    return value.strip("-") or "item"


def absolute_url(path: str) -> str:
    """Build an absolute URL using Flask request context."""
    if not path:
        return ""
    try:
        if request:
            if path.startswith(("http://", "https://")):
                return path
            return urljoin(request.url_root, path.lstrip("/"))
    except RuntimeError:
        pass
    base = (current_app and current_app.config.get("EXTERNAL_BASE_URL")) or ""
    if base:
        return urljoin(base, path.lstrip("/"))
    return path
