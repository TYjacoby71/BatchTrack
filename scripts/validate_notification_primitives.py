#!/usr/bin/env python3
"""Guard against new native browser dialog primitives in diffs.

Synopsis:
Scans added lines in a git diff range and fails when new native browser dialog
calls are introduced (`alert`, `confirm`, `prompt`) outside approved fallback
contexts.

Glossary:
- Native primitive: Browser-provided blocking dialog function.
- Added line: A `+` line in unified git diff output.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DIFF_FILTER = ("*.js", "*.html", "*.jinja2")
RAW_DIALOG_RE = re.compile(r"(?<![\w$.])(alert|confirm|prompt)\s*\(")
WINDOW_DIALOG_RE = re.compile(r"window\.(alert|confirm|prompt)\s*\(")
ALLOWED_WINDOW_FALLBACK_FILES = {
    "app/static/js/main.js",
}


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return proc.stdout


def _resolve_base_ref(explicit: str | None) -> str:
    if explicit:
        return explicit
    for candidate in ("origin/main", "origin/master", "HEAD~1"):
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", candidate],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return candidate
    return "HEAD~1"


def _extract_added_lines(base_ref: str) -> list[tuple[str, int, str]]:
    range_expr = f"{base_ref}...HEAD"
    args = [
        "diff",
        "--unified=0",
        "--no-color",
        range_expr,
        "--",
        *DIFF_FILTER,
    ]
    diff = _run_git(args)
    added: list[tuple[str, int, str]] = []
    current_file: str | None = None
    new_line_no = 0

    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
            continue
        if raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            new_line_no = int(match.group(1)) if match else 0
            continue
        if current_file is None:
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            added.append((current_file, new_line_no, raw[1:]))
            new_line_no += 1
        elif raw.startswith("-") and not raw.startswith("---"):
            continue
        else:
            new_line_no += 1
    return added


def _line_allows_window_fallback(path: str, line: str) -> bool:
    if path in ALLOWED_WINDOW_FALLBACK_FILES:
        return True
    stripped = line.strip()
    if stripped.startswith("//"):
        return True
    return (
        "return window.confirm(" in line
        or "return window.prompt(" in line
        or ": window.confirm(" in line
        or ": window.prompt(" in line
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate native notification primitive usage in added lines.")
    parser.add_argument("--base-ref", default=None, help="Git base ref for diff range (default: auto-resolve).")
    args = parser.parse_args()

    base_ref = _resolve_base_ref(args.base_ref)
    added_lines = _extract_added_lines(base_ref)
    violations: list[str] = []

    for path, line_no, line in added_lines:
        if path.startswith("app/static/dist/"):
            # Dist assets are generated output and mirror source behavior.
            continue
        stripped = line.strip()
        if stripped.startswith("//"):
            continue

        raw_match = RAW_DIALOG_RE.search(line)
        if raw_match:
            violations.append(
                f"{path}:{line_no}: Added native `{raw_match.group(1)}(...)` call; use shared notification helpers."
            )
            continue

        window_match = WINDOW_DIALOG_RE.search(line)
        if window_match and not _line_allows_window_fallback(path, line):
            violations.append(
                f"{path}:{line_no}: Added `{window_match.group(0)}` outside approved fallback contexts."
            )

    if violations:
        print("Notification primitive guard failed:")
        for violation in violations:
            print(f" - {violation}")
        return 1

    print("Notification primitive guard passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
