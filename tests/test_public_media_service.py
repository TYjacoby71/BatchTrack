from __future__ import annotations

from pathlib import Path

from app.services import public_media_service


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_build_youtube_embed_url_parses_common_link_formats():
    video_id, embed_url = public_media_service._build_youtube_embed_url(
        "https://youtu.be/dQw4w9WgXcQ?t=43"
    )
    assert video_id == "dQw4w9WgXcQ"
    assert (
        embed_url
        == "https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1&playsinline=1&start=43"
    )

    short_id, short_embed_url = public_media_service._build_youtube_embed_url(
        "https://www.youtube.com/shorts/dQw4w9WgXcQ"
    )
    assert short_id == "dQw4w9WgXcQ"
    assert (
        short_embed_url
        == "https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1&playsinline=1"
    )


def test_resolve_first_media_from_folder_prefers_youtube_url_files(app, tmp_path):
    static_root = tmp_path / "static"
    folder = static_root / "images" / "homepage" / "hero" / "primary"
    _write_text(
        folder / "youtube.url",
        "[InternetShortcut]\nURL=https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    _write_bytes(folder / "backup.mp4", b"video")

    app.static_folder = str(static_root)
    with app.app_context():
        resolved = public_media_service.resolve_first_media_from_folder(
            "images/homepage/hero/primary",
            allow_images=True,
            allow_videos=True,
        )

    assert resolved is not None
    assert resolved.get("kind") == "youtube"
    assert (
        resolved.get("embed_url")
        == "https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0&modestbranding=1&playsinline=1"
    )


def test_resolve_first_media_skips_invalid_url_and_falls_back_to_local_video(app, tmp_path):
    static_root = tmp_path / "static"
    folder = static_root / "images" / "homepage" / "hero" / "primary"
    _write_text(folder / "youtube.url", "this is not a youtube link")
    _write_bytes(folder / "backup.mp4", b"video")

    app.static_folder = str(static_root)
    with app.app_context():
        resolved = public_media_service.resolve_first_media_from_folder(
            "images/homepage/hero/primary",
            allow_images=True,
            allow_videos=True,
        )

    assert resolved is not None
    assert resolved.get("kind") == "video"
    assert resolved.get("path") == "images/homepage/hero/primary/backup.mp4"


def test_build_media_signature_uses_youtube_embed_url():
    signature = public_media_service.build_media_signature(
        [
            (
                "hero",
                {
                    "kind": "youtube",
                    "embed_url": "https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0",
                },
            ),
            ("final-cta", {"kind": "video", "path": "images/homepage/final.mp4"}),
        ]
    )
    assert "hero:youtube:https://www.youtube.com/embed/dQw4w9WgXcQ?rel=0" in signature
    assert "final-cta:video:images/homepage/final.mp4" in signature
