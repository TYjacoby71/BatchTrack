#!/usr/bin/env python3
"""PR documentation guard validator.

Synopsis:
Validates documentation standards for pull requests by inspecting changed files
and enforcing module/file schemas, APP_DICTIONARY coverage, and changelog
requirements for application changes.

Glossary:
- Changed file set: Paths reported by git diff for the PR/staged range.
- Functional unit header: Structured comment block with Purpose/Inputs/Outputs.
- Dictionary coverage: Presence of changed app paths in APP_DICTIONARY entries.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DICTIONARY_PATH = REPO_ROOT / "docs/system/APP_DICTIONARY.md"
CHANGELOG_INDEX_PATH = REPO_ROOT / "docs/changelog/CHANGELOG_INDEX.md"

CHANGELOG_ENTRY_PATH_RE = re.compile(r"^docs/changelog/\d{4}-\d{2}-\d{2}-.+\.md$")
ENTRY_SCHEMA_RE = re.compile(r"^- \*\*([^*]+)\*\* → (.+)$")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
BACKTICK_RE = re.compile(r"`([^`]+)`")
REPO_ROOT_PREFIXES = ("app/", "docs/", "scripts/", ".github/", "tests/", "marketing/", "migrations/")


# --- Changed file descriptor ---
# Purpose: Represent a changed path from git name-status output.
# Inputs: Git status code, current path, and optional old path for renames.
# Outputs: Dataclass instance used by all validation routines.
@dataclass(frozen=True)
class ChangedFile:
    status: str
    path: str
    old_path: str | None = None


# --- Run git command helper ---
# Purpose: Execute a git command and return stdout as text.
# Inputs: Git argument list and optional allow_failure behavior.
# Outputs: Command stdout string; raises RuntimeError on failure by default.
def _run_git(args: list[str], *, allow_failure: bool = False) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 and not allow_failure:
        raise RuntimeError(proc.stderr.strip() or "git command failed")
    return proc.stdout.strip()


# --- Check git ref existence ---
# Purpose: Verify whether a candidate ref is resolvable in this repository.
# Inputs: Ref string (e.g., origin/main).
# Outputs: True when ref exists, otherwise False.
def _git_ref_exists(ref: str) -> bool:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


# --- Resolve base ref ---
# Purpose: Choose the base ref used for PR-range diff detection.
# Inputs: Optional explicit base ref argument.
# Outputs: Resolved git ref string for diff comparison.
def _resolve_base_ref(explicit_base_ref: str | None) -> str:
    if explicit_base_ref:
        return explicit_base_ref

    github_base_ref = os.getenv("GITHUB_BASE_REF")
    if github_base_ref:
        candidate = f"origin/{github_base_ref}"
        if _git_ref_exists(candidate):
            return candidate

    for candidate in ("origin/main", "origin/master"):
        if _git_ref_exists(candidate):
            return candidate

    return "HEAD~1"


# --- Parse git name-status output ---
# Purpose: Convert git diff --name-status output into structured records.
# Inputs: Raw stdout text from git diff name-status.
# Outputs: List of ChangedFile records.
def _parse_name_status(output: str) -> list[ChangedFile]:
    changed: list[ChangedFile] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status_code = parts[0].strip()
        status = status_code[0]

        if status in {"R", "C"} and len(parts) >= 3:
            changed.append(ChangedFile(status=status, old_path=parts[1], path=parts[2]))
            continue

        if len(parts) >= 2:
            changed.append(ChangedFile(status=status, path=parts[1]))

    return changed


# --- Collect changed files ---
# Purpose: Build the effective changed-file set from staged/base-ref diff.
# Inputs: Parsed CLI args for staged/base/explicit file controls.
# Outputs: List of changed file descriptors for validation.
def _collect_changed_files(args: argparse.Namespace) -> list[ChangedFile]:
    if args.changed_file:
        records: list[ChangedFile] = []
        for path in args.changed_file:
            records.append(ChangedFile(status="M", path=path))
        return records

    if args.staged:
        output = _run_git(["diff", "--name-status", "--cached", "--diff-filter=ACMR"], allow_failure=True)
        return _parse_name_status(output)

    base_ref = _resolve_base_ref(args.base_ref)
    range_expr = f"{base_ref}...HEAD"
    output = _run_git(["diff", "--name-status", "--diff-filter=ACMR", range_expr], allow_failure=True)
    records = _parse_name_status(output)
    if records:
        return records

    fallback_output = _run_git(["diff", "--name-status", "--diff-filter=ACMR", "HEAD~1...HEAD"], allow_failure=True)
    return _parse_name_status(fallback_output)


# --- Identify app/source file ---
# Purpose: Determine if a changed path is an application source file.
# Inputs: Repository-relative file path.
# Outputs: True when path should trigger dictionary/changelog obligations.
def _is_app_source_file(path: str) -> bool:
    return path.startswith("app/") and not path.startswith("app/marketing/")


# --- Read file text safely ---
# Purpose: Load UTF-8 text from a repository-relative path.
# Inputs: Relative path string.
# Outputs: File text, or empty string when file is missing/unreadable.
def _read_text(path: str) -> str:
    abs_path = REPO_ROOT / path
    try:
        return abs_path.read_text(encoding="utf-8")
    except Exception:
        return ""


# --- Validate PR-level requirements ---
# Purpose: Enforce changelog presence and index linkage whenever app code changes.
# Inputs: Changed files and mutable issues list.
# Outputs: Appends violation strings to issues when requirements are unmet.
def _validate_pr_level_requirements(changed: list[ChangedFile], issues: list[str]) -> None:
    app_changes = [entry for entry in changed if _is_app_source_file(entry.path)]
    if not app_changes:
        return

    touched_changelog_entries = [
        entry.path
        for entry in changed
        if CHANGELOG_ENTRY_PATH_RE.match(entry.path)
    ]
    if not touched_changelog_entries:
        issues.append(
            "App code changed but no dated changelog entry was added/updated in docs/changelog/."
        )
        return

    index_text = _read_text("docs/changelog/CHANGELOG_INDEX.md")
    if not index_text:
        issues.append("docs/changelog/CHANGELOG_INDEX.md is missing or unreadable.")
        return

    for entry_path in touched_changelog_entries:
        relative_name = entry_path.replace("docs/changelog/", "", 1)
        if relative_name not in index_text:
            issues.append(
                f"{entry_path}: Missing link in docs/changelog/CHANGELOG_INDEX.md."
            )


# --- Validate Python file schema ---
# Purpose: Enforce module synopsis/glossary and per-unit functional headers.
# Inputs: Changed Python path and mutable issues list.
# Outputs: Appends violation strings to issues.
def _validate_python_file_schema(path: str, issues: list[str]) -> None:
    src = _read_text(path)
    if not src:
        issues.append(f"{path}: Unable to read file for schema validation.")
        return

    try:
        tree = ast.parse(src)
    except SyntaxError as exc:
        issues.append(f"{path}: Syntax error blocks schema validation ({exc}).")
        return

    module_doc = ast.get_docstring(tree, clean=False) or ""
    lowered_doc = module_doc.lower()
    if "synopsis" not in lowered_doc or "glossary" not in lowered_doc:
        issues.append(
            f"{path}: Module docstring must include Synopsis and Glossary sections."
        )

    lines = src.splitlines()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue

        decorators = getattr(node, "decorator_list", []) or []
        start_line = min([node.lineno, *[decorator.lineno for decorator in decorators]])
        window = [
            line.strip()
            for line in lines[max(0, start_line - 9): start_line - 1]
            if line.strip()
        ]

        def has_prefix(prefix: str) -> bool:
            return any(line.startswith(prefix) for line in window)

        missing_bits: list[str] = []
        if not has_prefix("# ---"):
            missing_bits.append("header (# --- ... ---)")
        if not has_prefix("# Purpose:"):
            missing_bits.append("Purpose")
        if not has_prefix("# Inputs:"):
            missing_bits.append("Inputs")
        if not has_prefix("# Outputs:"):
            missing_bits.append("Outputs")

        if missing_bits:
            issues.append(
                f"{path}:{start_line} top-level unit '{node.name}' missing {', '.join(missing_bits)}."
            )


# --- Validate system-doc schema ---
# Purpose: Ensure changed system docs include required Synopsis/Glossary blocks.
# Inputs: Changed markdown path and mutable issues list.
# Outputs: Appends violation strings to issues.
def _validate_system_doc_schema(path: str, issues: list[str]) -> None:
    text = _read_text(path)
    if not text:
        issues.append(f"{path}: Unable to read markdown file for validation.")
        return

    if not re.search(r"^##\s+Synopsis\b", text, flags=re.MULTILINE):
        issues.append(f"{path}: Missing required '## Synopsis' section.")
    if not re.search(r"^##\s+Glossary\b", text, flags=re.MULTILINE):
        issues.append(f"{path}: Missing required '## Glossary' section.")


# --- Validate changelog entry schema ---
# Purpose: Ensure changed changelog entries follow required section structure.
# Inputs: Changed changelog markdown path and mutable issues list.
# Outputs: Appends violation strings to issues.
def _validate_changelog_entry_schema(path: str, issues: list[str]) -> None:
    text = _read_text(path)
    if not text:
        issues.append(f"{path}: Unable to read changelog entry.")
        return

    required_sections = (
        "## Summary",
        "## Problems Solved",
        "## Key Changes",
        "## Files Modified",
    )
    for section in required_sections:
        if section not in text:
            issues.append(f"{path}: Missing required section '{section}'.")


# --- Validate dictionary schema/coverage ---
# Purpose: Enforce APP_DICTIONARY entry schema, uniqueness, and changed-path coverage.
# Inputs: Changed file records and mutable issues list.
# Outputs: Appends violation strings to issues.
def _validate_dictionary_schema(changed: list[ChangedFile], issues: list[str]) -> None:
    if not APP_DICTIONARY_PATH.exists():
        issues.append("docs/system/APP_DICTIONARY.md is missing.")
        return

    text = APP_DICTIONARY_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_layer_entries = False
    seen_terms: dict[str, int] = {}
    for idx, line in enumerate(lines, start=1):
        if re.match(r"^##\s+[1-5]\.\s+", line):
            in_layer_entries = True
            continue
        if line.startswith("## Contribution Rules"):
            in_layer_entries = False
            break
        if not in_layer_entries:
            continue

        if line.startswith("- **"):
            match = ENTRY_SCHEMA_RE.match(line.strip())
            if not match:
                issues.append(
                    f"docs/system/APP_DICTIONARY.md:{idx} invalid entry schema. "
                    "Expected '- **Term** → Description'."
                )
                continue
            term = match.group(1).strip().lower()
            seen_terms[term] = seen_terms.get(term, 0) + 1

    duplicates = sorted(term for term, count in seen_terms.items() if count > 1)
    for term in duplicates:
        issues.append(
            f"docs/system/APP_DICTIONARY.md: duplicate term detected (one-entry rule): '{term}'."
        )

    app_changed_paths = [entry.path for entry in changed if _is_app_source_file(entry.path)]
    for path in app_changed_paths:
        if f"`{path}`" not in text:
            issues.append(
                f"APP_DICTIONARY coverage missing for changed app file: {path}"
            )

    for entry in changed:
        if entry.status != "R" or not entry.old_path:
            continue
        if not _is_app_source_file(entry.path):
            continue
        if f"`{entry.path}`" not in text:
            issues.append(
                f"APP_DICTIONARY missing renamed path reference: {entry.path}"
            )
        if f"`{entry.old_path}`" in text:
            issues.append(
                f"APP_DICTIONARY still references moved path: {entry.old_path}"
            )


# --- Check path-like token ---
# Purpose: Decide whether a markdown/backtick token should be treated as a filesystem path.
# Inputs: Token string extracted from markdown content.
# Outputs: True if token appears to be a local file/directory reference.
def _looks_like_path(token: str) -> bool:
    if token.startswith(("http://", "https://", "mailto:", "#")):
        return False
    if any(char.isspace() for char in token):
        return False
    if token.startswith("/"):
        # Treat leading-slash tokens as routes by default, not repo paths.
        return False
    if token.startswith(REPO_ROOT_PREFIXES):
        return True
    if token.endswith(".md"):
        return True
    if "/" in token and token.endswith((".py", ".html", ".js", ".ts", ".yml", ".yaml", ".json", ".svg")):
        return True
    return False


# --- Resolve markdown target path ---
# Purpose: Resolve relative markdown/link token into an absolute filesystem path.
# Inputs: Token and base directory for relative resolution.
# Outputs: Absolute path candidate.
def _resolve_target(token: str, base_dir: Path) -> Path:
    clean = token.split("#", 1)[0].strip()
    if clean.startswith("/"):
        return REPO_ROOT / clean.lstrip("/")
    if clean.startswith(REPO_ROOT_PREFIXES):
        return REPO_ROOT / clean
    return (base_dir / clean).resolve()


# --- Validate APP_DICTIONARY links ---
# Purpose: Ensure file/location references in APP_DICTIONARY resolve to real paths.
# Inputs: Mutable issues list.
# Outputs: Appends violation strings to issues.
def _validate_dictionary_links(issues: list[str]) -> None:
    if not APP_DICTIONARY_PATH.exists():
        return

    text = APP_DICTIONARY_PATH.read_text(encoding="utf-8")
    base_dir = APP_DICTIONARY_PATH.parent

    candidates: set[str] = set()
    for token in BACKTICK_RE.findall(text):
        if _looks_like_path(token):
            candidates.add(token)
    for token in MARKDOWN_LINK_RE.findall(text):
        if _looks_like_path(token):
            candidates.add(token)

    for token in sorted(candidates):
        if token.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = _resolve_target(token, base_dir)

        if "*" in token:
            glob_pattern = token.split("#", 1)[0].strip().lstrip("/")
            if token.startswith(REPO_ROOT_PREFIXES) or token.startswith("/"):
                matches = list(REPO_ROOT.glob(glob_pattern))
            else:
                matches = list(base_dir.glob(glob_pattern))
            if not matches:
                issues.append(f"APP_DICTIONARY link target not found (glob): {token}")
            continue

        if token.endswith("/"):
            if not target.exists() or not target.is_dir():
                issues.append(f"APP_DICTIONARY directory target not found: {token}")
            continue

        if not target.exists():
            issues.append(f"APP_DICTIONARY link target not found: {token}")


# --- Validate changelog index links ---
# Purpose: Ensure markdown links in changelog index resolve to existing files.
# Inputs: Mutable issues list.
# Outputs: Appends violation strings to issues.
def _validate_changelog_index_links(issues: list[str]) -> None:
    if not CHANGELOG_INDEX_PATH.exists():
        issues.append("docs/changelog/CHANGELOG_INDEX.md is missing.")
        return

    text = CHANGELOG_INDEX_PATH.read_text(encoding="utf-8")
    base_dir = CHANGELOG_INDEX_PATH.parent

    for target_token in MARKDOWN_LINK_RE.findall(text):
        if target_token.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = _resolve_target(target_token, base_dir)
        if not target.exists():
            issues.append(
                f"CHANGELOG_INDEX broken link target: {target_token}"
            )


# --- Print validation issues ---
# Purpose: Emit a readable summary of guard failures for CI/pre-commit logs.
# Inputs: Issue message list.
# Outputs: Console output only.
def _print_issues(issues: list[str]) -> None:
    print("Documentation guard failed with the following issues:")
    for issue in issues:
        print(f"- {issue}")


# --- Main entrypoint ---
# Purpose: Parse CLI args, run all validators, and return process status.
# Inputs: CLI flags for base ref, staged mode, and explicit files.
# Outputs: Exit code 0 on success, 1 on violations.
def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PR documentation enforcement rules.")
    parser.add_argument("--base-ref", help="Base ref for git diff (e.g., origin/main).")
    parser.add_argument("--staged", action="store_true", help="Validate staged changes only.")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Explicit changed file path (repeatable).",
    )
    args = parser.parse_args()

    changed = _collect_changed_files(args)
    if not changed:
        print("Documentation guard: no changed files detected.")
        return 0

    issues: list[str] = []
    _validate_pr_level_requirements(changed, issues)

    for entry in changed:
        path = entry.path
        if path.endswith(".py") and (
            path.startswith("app/") or path.startswith("scripts/")
        ):
            _validate_python_file_schema(path, issues)
        if path.startswith("docs/system/") and path.endswith(".md"):
            _validate_system_doc_schema(path, issues)
        if CHANGELOG_ENTRY_PATH_RE.match(path):
            _validate_changelog_entry_schema(path, issues)

    _validate_dictionary_schema(changed, issues)
    _validate_dictionary_links(issues)
    _validate_changelog_index_links(issues)

    if issues:
        _print_issues(issues)
        return 1

    print("Documentation guard passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
