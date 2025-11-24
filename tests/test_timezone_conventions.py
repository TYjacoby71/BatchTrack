"""Guardrail tests enforcing timezone usage conventions.

These tests intentionally scan source code to ensure that:

1. `datetime.utcnow()` is never used (we standardize on timezone-aware UTC).
2. `datetime.now()` is always passed an explicit timezone argument such as
   `timezone.utc`, `pytz.UTC`, `tz=...`, or delegates to `TimezoneUtils`.

If this test fails, update the offending code path to use
`TimezoneUtils.utc_now()` or `datetime.now(timezone.utc)` as appropriate.
"""

from __future__ import annotations

from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Directories / files to scan for timezone usage. These cover the production
# code plus supporting scripts that ship with the project.
SCAN_TARGETS = [
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "app" / "utils" / "fault_log.py",
    PROJECT_ROOT / "app" / "utils" / "logging_helpers.py",
    PROJECT_ROOT / "reset_database.py",
]

# Context markers that indicate a `datetime.now()` call is timezone-aware.
ALLOWED_NOW_CONTEXT = (
    "timezone.utc",
    "pytz.",
    "tz=",
    "TimezoneUtils",
    "datetime.now(tz",
)


def _iter_python_files():
    for target in SCAN_TARGETS:
        if target.is_dir():
            for path in target.rglob("*.py"):
                # Skip virtual environments, caches, etc.
                if "__pycache__" in path.parts:
                    continue
                yield path
        elif target.suffix == ".py" and target.exists():
            yield target


def _line_number(text: str, index: int) -> int:
    """Return 1-based line number for the text index."""
    return text.count("\n", 0, index) + 1


def test_no_naive_datetime_usage():
    """Ensure no code uses naive datetime helpers."""

    failures: list[str] = []
    utcnow_pattern = re.compile(r"datetime\.utcnow\s*\(")
    now_pattern = re.compile(r"datetime\.now\s*\(")

    for path in sorted(_iter_python_files()):
        text = path.read_text(encoding="utf-8")

        # 1. Forbid datetime.utcnow
        for match in utcnow_pattern.finditer(text):
            line_no = _line_number(text, match.start())
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}:{line_no} uses forbidden datetime.utcnow()"
            )

        # 2. Require timezone context for datetime.now
        for match in now_pattern.finditer(text):
            line_no = _line_number(text, match.start())

            # Capture contextual snippet (covers multi-line calls).
            snippet = text[match.start(): match.start() + 120]

            if any(marker in snippet for marker in ALLOWED_NOW_CONTEXT):
                continue

            # Allow occurrences inside comments or strings by doing a light
            # check on the immediate line content.
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.start())
            if line_end == -1:
                line_end = len(text)
            line_text = text[line_start:line_end].strip()

            if line_text.startswith("#") or line_text.startswith("'") or line_text.startswith('"'):
                continue

            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}:{line_no} should use timezone-aware datetime.now("  # noqa: E501
            )

    assert not failures, "\n".join(["Timezone guardrails failed:"] + failures)
