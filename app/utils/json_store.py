import contextlib
import json
import os
import tempfile
from pathlib import Path

try:  # pragma: no cover - Windows fallback
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


@contextlib.contextmanager
def _file_lock(lock_path: Path, exclusive: bool):
    if fcntl is None:
        # No-op lock for platforms without fcntl (should not be used in production Linux)
        yield
        return

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock_file:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(lock_file.fileno(), mode)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def read_json_file(path: str | os.PathLike, default=None):
    file_path = Path(path)
    if not file_path.exists():
        return default

    lock_path = file_path.with_suffix(file_path.suffix + '.lock')

    with _file_lock(lock_path, exclusive=False):
        try:
            with file_path.open('r', encoding='utf-8') as fh:
                return json.load(fh)
        except json.JSONDecodeError:
            return default
        except FileNotFoundError:
            return default


def write_json_file(path: str | os.PathLike, data, *, indent: int = 2) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = file_path.with_suffix(file_path.suffix + '.lock')

    with _file_lock(lock_path, exclusive=True):
        fd, tmp_name = tempfile.mkstemp(dir=str(file_path.parent), prefix=f'.{file_path.name}.', suffix='.tmp')
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as tmp:
                json.dump(data, tmp, indent=indent)
                tmp.flush()
                os.fsync(tmp.fileno())

            os.replace(tmp_path, file_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except FileNotFoundError:  # pragma: no cover
                    pass
