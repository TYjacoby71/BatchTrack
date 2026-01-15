"""Shared runner helpers for numbered SI pipeline wrappers."""

from __future__ import annotations

from typing import Iterable


def _strip_flag_argv(argv: list[str], flag: str) -> list[str]:
    """Remove occurrences of `flag` and its following value from argv."""
    out: list[str] = []
    skip_next = False
    for a in argv:
        if skip_next:
            skip_next = False
            continue
        if a == flag:
            skip_next = True
            continue
        out.append(a)
    return out


def build_stage_argv(stage: str, argv: list[str]) -> list[str]:
    """Force a run_pre_ai_pipeline stage, ignoring any user-provided --stage."""
    cleaned = _strip_flag_argv(list(argv or []), "--stage")
    return ["--stage", str(stage), *cleaned]

