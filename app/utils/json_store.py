from __future__ import annotations

import contextlib
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator, Union

try:  # pragma: no cover - Windows fallback
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

PathType = Union[str, os.PathLike[str]]

__all__ = ["read_json_file", "write_json_file"]


@contextlib.contextmanager
def _file_lock(lock_path: Path, exclusive: bool) -> Iterator[None]:
    """
    Cross-process advisory file lock using ``fcntl`` when available.

    On platforms without ``fcntl`` (e.g., Windows), the lock becomes a no-op, which
    is acceptable for local tooling but should be avoided for concurrent production
    writes.
    """
    if fcntl is None:
        yield
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock_file:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(lock_file.fileno(), mode)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _clone_default(default: Any) -> Any:
    return copy.deepcopy(default) if default is not None else default


def read_json_file(path: PathType, default: Any = None) -> Any:
    """
    Read a JSON file with shared locking and safe fallbacks.

    Args:
        path: File path to read from.
        default: Value returned when the file is missing or invalid.
    """
    file_path = Path(path)
    if not file_path.exists():
        return _clone_default(default)

    lock_path = file_path.with_suffix(file_path.suffix + ".lock")

    with _file_lock(lock_path, exclusive=False):
        try:
            with file_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, FileNotFoundError):
            return _clone_default(default)


def write_json_file(path: PathType, data: Any, *, indent: int = 2) -> None:
    """
    Atomically write JSON data to disk using a temp file + rename dance.
    """
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = file_path.with_suffix(file_path.suffix + ".lock")

    with _file_lock(lock_path, exclusive=True):
        fd, tmp_name = tempfile.mkstemp(
            dir=str(file_path.parent), prefix=f".{file_path.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                json.dump(data, tmp, indent=indent)
                tmp.flush()
                os.fsync(tmp.fileno())

            os.replace(tmp_path, file_path)
        finally:
            if tmp_path.exists():
                with contextlib.suppress(FileNotFoundError):
                    tmp_path.unlink()
