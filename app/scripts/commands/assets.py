"""Static asset pipeline and operations commands."""

from pathlib import Path
import subprocess

import click
from flask import current_app
from flask.cli import with_appcontext


def _run_npm_script(script_name: str) -> None:
    project_root = Path(current_app.root_path).parent
    command = ["npm", "run", script_name]
    try:
        subprocess.run(command, cwd=project_root, check=True)
    except FileNotFoundError as exc:
        raise click.ClickException(
            "npm is not installed or not available on PATH. Install Node.js/npm first."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(
            f"Asset build failed while running: {' '.join(command)}"
        ) from exc


@click.command("build-assets")
@with_appcontext
def build_assets_command():
    """Build hashed JS assets and manifest via the esbuild pipeline."""
    _run_npm_script("build:assets")
    click.echo("Asset build complete: app/static/dist/manifest.json updated.")


@click.command("build-soap-assets")
@with_appcontext
def build_soap_assets_command():
    """Build Soap-only bundle entry via scoped esbuild pipeline."""
    _run_npm_script("build:soap-bundle")
    click.echo("Soap asset build complete.")


@click.command("minify-static")
@with_appcontext
def minify_static_command():
    """Deprecated compatibility alias for build-assets."""
    click.echo(
        "WARNING: `flask minify-static` is deprecated. "
        "Using hashed bundler pipeline via `flask build-assets`."
    )
    _run_npm_script("build:assets")
    click.echo("Asset build complete: app/static/dist/manifest.json updated.")


ASSET_COMMANDS = [
    build_assets_command,
    build_soap_assets_command,
    minify_static_command,
]

