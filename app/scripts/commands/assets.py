"""Static asset pipeline and operations commands."""

from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("minify-static")
@with_appcontext
def minify_static_command():
    """Generate minified .min.js/.min.css assets under the static folder."""
    try:
        from rcssmin import cssmin
        from rjsmin import jsmin
    except ImportError as exc:
        raise click.ClickException(
            "Missing minifier dependency. Install `rjsmin` and `rcssmin` to run this command."
        ) from exc

    static_folder = Path(current_app.static_folder or "static")
    if not static_folder.is_dir():
        raise click.ClickException(f"Static folder not found: {static_folder}")

    processed = 0
    written = 0
    unchanged = 0
    failed = 0

    for source_path in sorted(static_folder.rglob("*")):
        if not source_path.is_file():
            continue
        suffix = source_path.suffix.lower()
        if suffix not in {".js", ".css"}:
            continue
        if source_path.name.endswith(f".min{suffix}"):
            continue
        if suffix == ".js" and source_path.name.endswith(".config.js"):
            # Build-time config files are not served as browser assets.
            continue

        processed += 1
        target_path = source_path.with_name(f"{source_path.stem}.min{suffix}")

        try:
            source_text = source_path.read_text(encoding="utf-8")
            minified_text = jsmin(source_text) if suffix == ".js" else cssmin(source_text)
            if minified_text and not minified_text.endswith("\n"):
                minified_text += "\n"

            if target_path.exists():
                existing_text = target_path.read_text(encoding="utf-8")
                if existing_text == minified_text:
                    unchanged += 1
                    continue

            target_path.write_text(minified_text, encoding="utf-8")
            written += 1
            click.echo(
                f"minified: {source_path.relative_to(static_folder).as_posix()} "
                f"-> {target_path.relative_to(static_folder).as_posix()}"
            )
        except Exception as exc:
            failed += 1
            click.echo(f"failed: {source_path.relative_to(static_folder).as_posix()} ({exc})")

    click.echo(
        f"Static minification complete. processed={processed}, written={written}, "
        f"unchanged={unchanged}, failed={failed}"
    )
    if failed:
        raise click.ClickException("One or more static assets failed to minify.")


ASSET_COMMANDS = [minify_static_command]

