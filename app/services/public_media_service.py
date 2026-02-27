"""Public media helpers for folder-based image/video slots.

Synopsis:
Resolves media assets for public pages using a simple convention:
each visual slot has a folder, and the first media file in that folder
is rendered.

Glossary:
- Media slot: A named UI surface (hero, card, testimonial photo, etc.).
- Folder-based media: Static asset lookup that does not require strict filenames.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

from flask import current_app, has_app_context

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".avif",
}
VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".ogg",
    ".mov",
    ".m4v",
}
YOUTUBE_LINK_EXTENSIONS = {
    ".url",
}
_YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YOUTUBE_IFRAME_SRC_RE = re.compile(r'src=["\']([^"\']+)["\']', re.IGNORECASE)
_YOUTUBE_TIMESTAMP_RE = re.compile(
    r"^(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?$",
    re.IGNORECASE,
)

HOMEPAGE_FEATURE_CARD_CATALOG: tuple[Dict[str, str], ...] = (
    {
        "slug": "recipe-tracking",
        "name": "Recipe Tracking",
        "summary": "Track every recipe, variation, and test in one clear timeline.",
        "icon": "BT",
        "folder": "images/homepage/features/recipe-tracking",
    },
    {
        "slug": "fifo-inventory",
        "name": "Inventory Management",
        "summary": "Keep FIFO inventory accurate with cost, lot, and expiration visibility.",
        "icon": "FI",
        "folder": "images/homepage/features/fifo-inventory",
    },
    {
        "slug": "batch-in-progress",
        "name": "Batch In Progress",
        "summary": "Run each batch with timers, notes, and change tracking from start to finish.",
        "icon": "AN",
        "folder": "images/homepage/features/batch-in-progress",
    },
)

HOMEPAGE_MORE_FEATURE_CARD_CATALOG: tuple[Dict[str, str], ...] = (
    {
        "slug": "more-fifo-inventory",
        "name": "FIFO Inventory",
        "summary": "FIFO-aware inventory keeps usage and costs tied to the right lots.",
        "icon": "TM",
        "folder": "images/homepage/features/more-fifo-inventory",
    },
    {
        "slug": "more-qr-code-labels",
        "name": "QR Code Labels",
        "summary": "Generate QR-linked labels so every product traces back to its batch record.",
        "icon": "QR",
        "folder": "images/homepage/features/more-qr-code-labels",
    },
    {
        "slug": "more-timer-management",
        "name": "Timer Management",
        "summary": "Keep every timer attached to its batch and get alerts before quality slips.",
        "icon": "MB",
        "folder": "images/homepage/features/more-timer-management",
    },
)

HOMEPAGE_INTEGRATION_TILE_CATALOG: tuple[Dict[str, str], ...] = (
    {
        "slug": "shopify",
        "name": "Shopify",
        "folder": "images/homepage/integrations/shopify",
        "fallback_logo": "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/shopify.svg",
    },
    {
        "slug": "etsy",
        "name": "Etsy",
        "folder": "images/homepage/integrations/etsy",
        "fallback_logo": "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/etsy.svg",
    },
    {
        "slug": "quickbooks",
        "name": "QuickBooks",
        "folder": "images/homepage/integrations/quickbooks",
        "fallback_logo": "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/quickbooks.svg",
    },
)

HOMEPAGE_MEDIA_SLOTS: tuple[Tuple[str, str], ...] = (
    ("hero-primary", "images/homepage/hero/primary"),
    ("final-cta-primary", "images/homepage/app-screenshots/final-cta"),
)


def _allowed_extensions(*, allow_images: bool, allow_videos: bool) -> set[str]:
    extensions: set[str] = set()
    if allow_images:
        extensions |= IMAGE_EXTENSIONS
    if allow_videos:
        extensions |= VIDEO_EXTENSIONS
        extensions |= YOUTUBE_LINK_EXTENSIONS
    return extensions


def _get_static_root() -> Path | None:
    if not has_app_context():
        return None
    static_folder = getattr(current_app, "static_folder", None)
    if not static_folder:
        return None
    return Path(static_folder)


def _list_media_files(
    folder_relative: str, *, allow_images: bool = True, allow_videos: bool = True
) -> List[Path]:
    static_root = _get_static_root()
    if static_root is None:
        return []
    relative_folder = str(folder_relative or "").strip().lstrip("/")
    if not relative_folder:
        return []
    folder_path = static_root / relative_folder
    allowed = _allowed_extensions(allow_images=allow_images, allow_videos=allow_videos)
    if not allowed:
        return []
    try:
        if not folder_path.is_dir():
            return []
        files = [
            item
            for item in folder_path.iterdir()
            if item.is_file()
            and not item.name.startswith(".")
            and item.suffix.lower() in allowed
        ]
    except OSError:
        return []
    return sorted(
        files,
        key=lambda path: (
            0 if path.suffix.lower() in YOUTUBE_LINK_EXTENSIONS else 1,
            path.name.lower(),
        ),
    )


def _parse_timestamp_to_seconds(value: str) -> int | None:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return None
    if candidate.isdigit():
        return int(candidate)
    if candidate.endswith("s") and candidate[:-1].isdigit():
        return int(candidate[:-1])
    match = _YOUTUBE_TIMESTAMP_RE.fullmatch(candidate)
    if not match:
        return None
    total = (
        int(match.group("hours") or 0) * 3600
        + int(match.group("minutes") or 0) * 60
        + int(match.group("seconds") or 0)
    )
    return total if total > 0 else None


def _extract_url_candidate(raw_text: str) -> str | None:
    text = str(raw_text or "").strip()
    if not text:
        return None

    iframe_match = _YOUTUBE_IFRAME_SRC_RE.search(text)
    if iframe_match:
        src_value = str(iframe_match.group(1) or "").strip()
        if src_value:
            return src_value

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.upper().startswith("URL="):
            parsed = line.split("=", 1)[1].strip()
            if parsed:
                return parsed
            continue
        if line.startswith(("https://", "http://", "//")):
            return line
        lowered = line.lower()
        if "youtube.com" in lowered or "youtu.be" in lowered:
            return line
        if _YOUTUBE_VIDEO_ID_RE.fullmatch(line):
            return line
    return None


def _normalize_youtube_candidate(raw_value: str) -> str:
    candidate = str(raw_value or "").strip()
    if not candidate:
        return ""
    if candidate.startswith("//"):
        return f"https:{candidate}"
    lowered = candidate.lower()
    if "://" not in candidate and lowered.startswith(
        (
            "youtube.com/",
            "www.youtube.com/",
            "m.youtube.com/",
            "youtube-nocookie.com/",
            "www.youtube-nocookie.com/",
            "youtu.be/",
            "www.youtu.be/",
        )
    ):
        return f"https://{candidate}"
    return candidate


def _extract_youtube_video_id(raw_value: str) -> tuple[str | None, int | None]:
    candidate = _normalize_youtube_candidate(raw_value)
    if not candidate:
        return None, None
    if _YOUTUBE_VIDEO_ID_RE.fullmatch(candidate):
        return candidate, None

    parsed = urlparse(candidate)
    host = str(parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    query = parse_qs(parsed.query or "")
    start_seconds = _parse_timestamp_to_seconds(
        str(query.get("start", [None])[0] or query.get("t", [None])[0] or "")
    )
    video_id: str | None = None

    if host == "youtu.be":
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments:
            video_id = segments[0]
    elif host in {"youtube.com", "youtube-nocookie.com"}:
        segments = [segment for segment in parsed.path.split("/") if segment]
        if segments:
            if segments[0] in {"embed", "shorts", "live"} and len(segments) > 1:
                video_id = segments[1]
            elif segments[0] == "watch":
                video_id = str(query.get("v", [None])[0] or "")
        if not video_id:
            video_id = str(query.get("v", [None])[0] or "")

    if not video_id or not _YOUTUBE_VIDEO_ID_RE.fullmatch(video_id):
        return None, None
    return video_id, start_seconds


def _build_youtube_embed_url(raw_value: str) -> tuple[str | None, str | None]:
    video_id, start_seconds = _extract_youtube_video_id(raw_value)
    if not video_id:
        return None, None
    params = {
        "rel": "0",
        "modestbranding": "1",
        "playsinline": "1",
    }
    if start_seconds:
        params["start"] = str(start_seconds)
    return video_id, f"https://www.youtube.com/embed/{video_id}?{urlencode(params)}"


def _read_link_file_target(path: Path) -> str | None:
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    target = _extract_url_candidate(content)
    return _normalize_youtube_candidate(target) if target else None


def _media_from_path(static_root: Path, path: Path) -> Dict[str, str] | None:
    ext = path.suffix.lower()
    if ext in YOUTUBE_LINK_EXTENSIONS:
        link_target = _read_link_file_target(path)
        video_id, embed_url = _build_youtube_embed_url(link_target or "")
        if not embed_url:
            return None
        kind = "youtube"
    elif ext in IMAGE_EXTENSIONS:
        kind = "image"
    elif ext in VIDEO_EXTENSIONS:
        kind = "video"
    else:
        return None
    try:
        relative_path = path.relative_to(static_root).as_posix()
    except ValueError:
        return None
    if kind == "youtube":
        return {
            "path": relative_path,
            "kind": kind,
            "url": link_target or "",
            "video_id": video_id or "",
            "embed_url": embed_url,
        }
    return {"path": relative_path, "kind": kind}


def resolve_first_media_from_folder(
    folder_relative: str, *, allow_images: bool = True, allow_videos: bool = True
) -> Dict[str, str] | None:
    """Resolve the first media file from a static folder."""
    static_root = _get_static_root()
    if static_root is None:
        return None
    files = _list_media_files(
        folder_relative,
        allow_images=allow_images,
        allow_videos=allow_videos,
    )
    if not files:
        return None
    for file_path in files:
        resolved = _media_from_path(static_root, file_path)
        if resolved is not None:
            return resolved
    return None


def resolve_media_list_from_folder(
    folder_relative: str,
    *,
    allow_images: bool = True,
    allow_videos: bool = True,
    limit: int | None = None,
) -> List[Dict[str, str]]:
    """Resolve sorted media files from a static folder."""
    static_root = _get_static_root()
    if static_root is None:
        return []
    files = _list_media_files(
        folder_relative,
        allow_images=allow_images,
        allow_videos=allow_videos,
    )
    media: List[Dict[str, str]] = []
    for file_path in files:
        if limit is not None and limit >= 0 and len(media) >= limit:
            break
        resolved = _media_from_path(static_root, file_path)
        if resolved is not None:
            media.append(resolved)
    return media


def _attach_card_media(cards: Iterable[Dict[str, str]]) -> List[Dict[str, Any]]:
    resolved_cards: List[Dict[str, Any]] = []
    for card in cards:
        resolved = dict(card)
        folder = str(card.get("folder") or "")
        media = resolve_first_media_from_folder(folder, allow_images=True, allow_videos=True)
        resolved["media"] = media
        resolved["image_path"] = media["path"] if media and media.get("kind") == "image" else None
        resolved_cards.append(resolved)
    return resolved_cards


def get_homepage_feature_cards() -> List[Dict[str, Any]]:
    """Return homepage feature cards with optional image/video media."""
    return _attach_card_media(HOMEPAGE_FEATURE_CARD_CATALOG)


def get_homepage_more_feature_cards() -> List[Dict[str, Any]]:
    """Return secondary homepage feature cards with optional image/video media."""
    return _attach_card_media(HOMEPAGE_MORE_FEATURE_CARD_CATALOG)


def get_homepage_integration_tiles() -> List[Dict[str, Any]]:
    """Return integration logo tiles with local media fallback."""
    tiles: List[Dict[str, Any]] = []
    for tile in HOMEPAGE_INTEGRATION_TILE_CATALOG:
        resolved = dict(tile)
        media = resolve_first_media_from_folder(
            str(tile.get("folder") or ""),
            allow_images=True,
            allow_videos=True,
        )
        resolved["media"] = media
        tiles.append(resolved)
    return tiles


def get_homepage_media_slots() -> Dict[str, Dict[str, str] | None]:
    """Return singleton homepage slot media (hero, final CTA, etc.)."""
    slots: Dict[str, Dict[str, str] | None] = {}
    for slot_key, folder in HOMEPAGE_MEDIA_SLOTS:
        slots[slot_key] = resolve_first_media_from_folder(
            folder,
            allow_images=True,
            allow_videos=True,
        )
    return slots


def get_homepage_testimonial_media() -> Dict[str, Dict[str, Dict[str, str] | None]]:
    """Return folder-based testimonial logo/photo media by customer key."""
    output: Dict[str, Dict[str, Dict[str, str] | None]] = {}
    for idx in range(1, 4):
        key = f"customer-{idx}"
        output[key] = {
            "logo": resolve_first_media_from_folder(
                f"images/homepage/testimonials/{key}/logo",
                allow_images=True,
                allow_videos=True,
            ),
            "photo": resolve_first_media_from_folder(
                f"images/homepage/testimonials/{key}/photo",
                allow_images=True,
                allow_videos=True,
            ),
        }
    return output


def get_help_media_for_sections(
    sections: Iterable[Dict[str, Any]]
) -> Dict[str, List[Dict[str, str]]]:
    """Return media lists for help overview sections keyed by section slug."""
    media_by_section: Dict[str, List[Dict[str, str]]] = {}
    for section in sections:
        slug = str(section.get("slug") or "").strip()
        if not slug:
            continue
        gallery = section.get("gallery") or []
        expected_count = len(gallery) if isinstance(gallery, list) else 0
        media_by_section[slug] = resolve_media_list_from_folder(
            f"images/help/{slug}",
            allow_images=True,
            allow_videos=True,
            limit=expected_count if expected_count > 0 else None,
        )
    return media_by_section


def build_media_signature(entries: Iterable[tuple[str, Dict[str, str] | None]]) -> str:
    """Build a deterministic signature for cache keys."""
    parts: List[str] = []
    for key, media in entries:
        safe_key = str(key or "")
        if not media:
            parts.append(f"{safe_key}:none")
            continue

        media_kind = str(media.get("kind") or "unknown")
        if media_kind == "youtube":
            value = str(
                media.get("embed_url") or media.get("url") or media.get("path") or ""
            )
        else:
            value = str(media.get("path") or "")
        if not value:
            parts.append(f"{safe_key}:none")
            continue
        parts.append(f"{safe_key}:{media_kind}:{value}")
    if not parts:
        return "none"
    return "|".join(parts)
