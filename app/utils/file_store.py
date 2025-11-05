"""Utility helpers for safe shared JSON file access.

These helpers provide coarse-grained file locking and atomic writes so that
admin endpoints which persist small JSON blobs do not corrupt files under
concurrent access. They deliberately avoid new third-party dependencies and are
Linux-friendly (fcntl-based) with a lightweight threading fallback for other
platforms.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Iterable, MutableMapping

_HAS_FCNTL = os.name != "nt"
if _HAS_FCNTL:  # pragma: no cover - fcntl unavailable on Windows CI
    import fcntl  # type: ignore


_THREAD_LOCKS: Dict[str, Lock] = {}


def _lock_file_path(target: Path) -> Path:
    return target.with_name(f".{target.name}.lock")


@contextmanager
def _exclusive_lock(target: Path) -> Iterable[None]:
    lock_path = _lock_file_path(target)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if _HAS_FCNTL:
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o666)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:  # pragma: no cover - simple system call wrapper
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
    else:  # pragma: no cover - fallback for non-POSIX platforms
        key = str(lock_path.resolve())
        lock = _THREAD_LOCKS.setdefault(key, Lock())
        lock.acquire()
        try:
            yield
        finally:
            lock.release()


def _atomic_dump_json(target: Path, payload: Any) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(payload, tmp_file, indent=2)
            tmp_file.write("\n")
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_path, target)
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass


def read_json(path: str | os.PathLike[str], *, default: Any | None = None) -> Any:
    """Read JSON data from *path* with an exclusive lock.

    Returns *default* if the file does not exist or cannot be decoded.
    """

    target = Path(path)
    with _exclusive_lock(target):
        if not target.exists():
            return default
        try:
            with target.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (json.JSONDecodeError, OSError):
            return default


def write_json(path: str | os.PathLike[str], payload: Any) -> None:
    """Atomically write *payload* as JSON to *path* under an exclusive lock."""

    target = Path(path)
    with _exclusive_lock(target):
        _atomic_dump_json(target, payload)


def update_json(
    path: str | os.PathLike[str],
    mutator: Callable[[MutableMapping[str, Any]], MutableMapping[str, Any]],
    *,
    default_factory: Callable[[], MutableMapping[str, Any]] | None = dict,
) -> MutableMapping[str, Any]:
    """Read-modify-write helper that keeps the file locked for the entire cycle."""

    target = Path(path)
    with _exclusive_lock(target):
        base: MutableMapping[str, Any]
        if target.exists():
            try:
                with target.open("r", encoding="utf-8") as handle:
                    base = json.load(handle)
            except (json.JSONDecodeError, OSError):
                base = default_factory() if default_factory else {}
        else:
            base = default_factory() if default_factory else {}

        updated = mutator(base)
        _atomic_dump_json(target, updated)
        return updated


__all__ = ["read_json", "write_json", "update_json"]
