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

from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

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
    {
        "slug": "zapier",
        "name": "Zapier",
        "folder": "images/homepage/integrations/zapier",
        "fallback_logo": "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/zapier.svg",
    },
    {
        "slug": "slack",
        "name": "Slack",
        "folder": "images/homepage/integrations/slack",
        "fallback_logo": "https://cdn.jsdelivr.net/npm/simple-icons@latest/icons/slack.svg",
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
    return sorted(files, key=lambda path: path.name.lower())


def _media_from_path(static_root: Path, path: Path) -> Dict[str, str] | None:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        kind = "image"
    elif ext in VIDEO_EXTENSIONS:
        kind = "video"
    else:
        return None
    try:
        relative_path = path.relative_to(static_root).as_posix()
    except ValueError:
        return None
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
    return _media_from_path(static_root, files[0])


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
    if limit is not None and limit >= 0:
        files = files[:limit]
    media: List[Dict[str, str]] = []
    for file_path in files:
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
        if media and media.get("path"):
            parts.append(
                f"{safe_key}:{media.get('kind') or 'unknown'}:{media.get('path')}"
            )
        else:
            parts.append(f"{safe_key}:none")
    if not parts:
        return "none"
    return "|".join(parts)
