#!/usr/bin/env python3
"""Migration integrity guard validator.

Synopsis:
Validates Alembic migration integrity by checking revision uniqueness, dependency
links, revision ID length, and head-count expectations.

Glossary:
- Revision ID: Alembic migration identifier string.
- Down revision: Parent revision (or revisions) this migration depends on.
- Head: A revision not referenced by any other migration as a down revision.
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations" / "versions"
MAX_REVISION_ID_LENGTH = 32


@dataclass(frozen=True)
class MigrationMeta:
    path: Path
    revision: str
    down_revisions: tuple[str, ...]


def _parse_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _parse_down_revisions(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Constant) and node.value is None:
        return ()
    single = _parse_string(node)
    if single is not None:
        return (single,)
    if isinstance(node, (ast.Tuple, ast.List)):
        parsed: list[str] = []
        for item in node.elts:
            text = _parse_string(item)
            if text is None:
                raise ValueError("down_revision tuple/list contains non-string element")
            parsed.append(text)
        return tuple(parsed)
    raise ValueError("down_revision must be None, string, tuple[str], or list[str]")


def _collect_migrations() -> tuple[list[MigrationMeta], list[str]]:
    issues: list[str] = []
    migrations: list[MigrationMeta] = []

    if not MIGRATIONS_DIR.exists():
        return migrations, [f"{MIGRATIONS_DIR} does not exist."]

    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src, filename=str(path))
        revision_node: ast.AST | None = None
        down_revision_node: ast.AST | None = None

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "revision":
                        revision_node = node.value
                    elif target.id == "down_revision":
                        down_revision_node = node.value

        if revision_node is None:
            issues.append(f"{path}: missing required assignment `revision = ...`")
            continue
        if down_revision_node is None:
            issues.append(f"{path}: missing required assignment `down_revision = ...`")
            continue

        revision = _parse_string(revision_node)
        if not revision:
            issues.append(f"{path}: revision must be a non-empty string literal")
            continue
        if len(revision) > MAX_REVISION_ID_LENGTH:
            issues.append(
                f"{path}: revision '{revision}' exceeds {MAX_REVISION_ID_LENGTH} characters"
            )
            continue

        try:
            down_revisions = _parse_down_revisions(down_revision_node)
        except ValueError as exc:
            issues.append(f"{path}: {exc}")
            continue

        migrations.append(
            MigrationMeta(path=path, revision=revision, down_revisions=down_revisions)
        )

    return migrations, issues


def _validate_relationships(
    migrations: list[MigrationMeta], *, allow_multiple_heads: bool
) -> list[str]:
    issues: list[str] = []
    revision_to_path: dict[str, Path] = {}

    for migration in migrations:
        if migration.revision in revision_to_path:
            issues.append(
                "Duplicate revision ID "
                f"'{migration.revision}' in {revision_to_path[migration.revision]} and {migration.path}"
            )
            continue
        revision_to_path[migration.revision] = migration.path

    for migration in migrations:
        for down_revision in migration.down_revisions:
            if down_revision not in revision_to_path:
                issues.append(
                    f"{migration.path}: down_revision '{down_revision}' does not exist in migrations/versions"
                )

    referenced_revisions = {
        down_revision
        for migration in migrations
        for down_revision in migration.down_revisions
    }
    heads = [
        migration
        for migration in migrations
        if migration.revision not in referenced_revisions
    ]
    if not heads:
        issues.append("No Alembic head revision found.")
    elif len(heads) > 1 and not allow_multiple_heads:
        head_list = ", ".join(
            f"{migration.revision} ({migration.path.name})" for migration in heads
        )
        issues.append(
            "Multiple Alembic heads detected (expected 1): "
            f"{head_list}. Create a merge migration or pass --allow-multiple-heads."
        )

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Alembic migration integrity.")
    parser.add_argument(
        "--allow-multiple-heads",
        action="store_true",
        help="Allow multiple Alembic heads without failing.",
    )
    args = parser.parse_args()

    migrations, parse_issues = _collect_migrations()
    issues = list(parse_issues)
    issues.extend(
        _validate_relationships(
            migrations, allow_multiple_heads=args.allow_multiple_heads
        )
    )

    if issues:
        print("Migration integrity guard failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print(
        f"Migration integrity guard passed ({len(migrations)} revisions, max revision length {MAX_REVISION_ID_LENGTH})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
