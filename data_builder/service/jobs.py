from __future__ import annotations

import os
import shlex
import subprocess
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class JobInfo:
    id: str
    command: list[str]
    cwd: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    pid: int | None = None
    returncode: int | None = None
    status: str = "queued"  # queued|running|finished|failed
    log_path: str | None = None
    error: str | None = None


_LOCK = threading.Lock()
_JOBS: dict[str, JobInfo] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jobs_dir() -> Path:
    base = Path(os.environ.get("DATA_BUILDER_SERVICE_LOG_DIR", "logs/data_builder/service"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def list_jobs(limit: int = 50) -> list[JobInfo]:
    with _LOCK:
        jobs = list(_JOBS.values())
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs[: max(1, min(500, limit))]


def get_job(job_id: str) -> JobInfo | None:
    with _LOCK:
        return _JOBS.get(job_id)


def job_to_dict(job: JobInfo) -> dict[str, Any]:
    return asdict(job)


def _validate_command(cmd: list[str]) -> None:
    """
    Not a whitelist, but a guardrail:
    - must invoke python (so it stays in-repo)
    - must target something under ./data_builder/
    """
    if not cmd:
        raise ValueError("Empty command")
    exe = Path(cmd[0]).name
    if exe not in {"python3", "python"}:
        raise ValueError("Command must start with python3/python")
    if len(cmd) < 2:
        raise ValueError("Command must include a script/module")

    target = cmd[1]
    if target == "-m":
        if len(cmd) < 3:
            raise ValueError("python -m requires a module name")
        module = cmd[2]
        if not (module == "data_builder" or module.startswith("data_builder.")):
            raise ValueError("python -m must target data_builder.*")
        return

    # Script path
    p = Path(target)
    if p.is_absolute():
        raise ValueError("Use a relative script path under data_builder/")
    norm = (Path("/workspace") / p).resolve()
    if not str(norm).startswith(str(Path("/workspace/data_builder").resolve()) + os.sep):
        raise ValueError("Script must be under ./data_builder/")


def start_job_from_command(command_text: str, *, cwd: str = "/workspace") -> JobInfo:
    cmd = shlex.split(command_text)
    _validate_command(cmd)

    job_id = uuid.uuid4().hex
    job = JobInfo(
        id=job_id,
        command=cmd,
        cwd=cwd,
        created_at=_now_iso(),
        status="queued",
    )

    log_path = str((_jobs_dir() / f"{job_id}.log").resolve())
    job.log_path = log_path

    with _LOCK:
        _JOBS[job_id] = job

    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return job


def _run_job(job_id: str) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.status = "running"
        job.started_at = _now_iso()

    job = get_job(job_id)
    if not job:
        return

    try:
        if not os.path.isdir(job.cwd):
            raise RuntimeError(f"Job cwd does not exist: {job.cwd}")

        log_path = job.log_path or str((_jobs_dir() / f"{job_id}.log").resolve())
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

        env = dict(os.environ)
        # If you set DATA_BUILDER_DATABASE_URL, expose it as DATABASE_URL for scripts.
        if env.get("DATA_BUILDER_DATABASE_URL") and not env.get("DATABASE_URL"):
            env["DATABASE_URL"] = env["DATA_BUILDER_DATABASE_URL"]

        with open(log_path, "ab", buffering=0) as f:
            f.write(f"[{_now_iso()}] START: {' '.join(job.command)}\n".encode("utf-8"))
            proc = subprocess.Popen(
                job.command,
                cwd=job.cwd,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=env,
            )
            with _LOCK:
                j = _JOBS.get(job_id)
                if j:
                    j.pid = proc.pid

            rc = proc.wait()
            with _LOCK:
                j = _JOBS.get(job_id)
                if j:
                    j.returncode = rc
                    j.finished_at = _now_iso()
                    j.status = "finished" if rc == 0 else "failed"
            f.write(f"[{_now_iso()}] END rc={rc}\n".encode("utf-8"))
    except Exception as exc:
        with _LOCK:
            j = _JOBS.get(job_id)
            if j:
                j.returncode = -1
                j.finished_at = _now_iso()
                j.status = "failed"
                j.error = str(exc)
        try:
            log_path = get_job(job_id).log_path if get_job(job_id) else None
            if log_path:
                with open(log_path, "ab", buffering=0) as f:
                    f.write(f"[{_now_iso()}] ERROR: {exc!r}\n".encode("utf-8"))
        except Exception:
            pass


def read_job_log_tail(job_id: str, *, max_bytes: int = 64_000) -> str:
    job = get_job(job_id)
    if not job or not job.log_path:
        raise FileNotFoundError("Job or log not found.")
    path = Path(job.log_path)
    if not path.exists():
        raise FileNotFoundError("Job log not found.")
    size = path.stat().st_size
    start = max(0, size - max(1, min(2_000_000, max_bytes)))
    with open(path, "rb") as f:
        f.seek(start)
        data = f.read()
    if start > 0:
        nl = data.find(b"\n")
        if nl != -1:
            data = data[nl + 1 :]
    return data.decode("utf-8", errors="replace")

