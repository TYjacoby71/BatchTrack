from __future__ import annotations

import os
import subprocess
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class JobInfo:
    id: str
    name: str
    command: list[str]
    cwd: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    pid: int | None = None
    returncode: int | None = None
    status: str = "queued"  # queued|running|finished|failed
    log_path: str | None = None


_LOCK = threading.Lock()
_JOBS: dict[str, JobInfo] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_job(job_id: str) -> JobInfo | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return job


def list_jobs(limit: int = 50) -> list[JobInfo]:
    with _LOCK:
        jobs = list(_JOBS.values())
    jobs.sort(key=lambda j: j.created_at, reverse=True)
    return jobs[: max(1, min(500, limit))]


def _jobs_dir() -> Path:
    # Keep logs in the repo so they persist in Replit filesystem.
    base = Path(os.environ.get("DATA_BUILDER_SERVICE_LOG_DIR", "logs/data_builder_service"))
    base.mkdir(parents=True, exist_ok=True)
    return base


def _allowed_jobs() -> dict[str, dict[str, Any]]:
    """
    Whitelisted jobs only (avoid turning this into a remote command runner).
    """
    return {
        "tgsc_scrape": {
            "description": "Run TGSC scraper (writes JSON into data_builder artifacts).",
            "base_cmd": ["python3", "data_builder/scrapers/tgsc_scraper.py"],
            "allowed_args": {
                "max_ingredients": ("--max-ingredients", int),
                "max_workers": ("--max-workers", int),
                "resume": ("--resume", bool),
            },
        },
        "compile_ingredients": {
            "description": "Run ingredient compiler loop.",
            "base_cmd": ["python3", "-m", "data_builder.ingredients.compiler"],
            "allowed_args": {
                "max_ingredients": ("--max-ingredients", int),
            },
        },
    }


def start_job(name: str, args: dict[str, Any] | None = None, *, cwd: str = "/workspace") -> JobInfo:
    spec = _allowed_jobs().get(name)
    if not spec:
        raise ValueError(f"Unknown job {name!r}.")

    cmd: list[str] = list(spec["base_cmd"])
    args = dict(args or {})
    for key, value in args.items():
        if key not in spec["allowed_args"]:
            raise ValueError(f"Argument {key!r} not allowed for job {name!r}.")
        flag, caster = spec["allowed_args"][key]
        if caster is bool:
            if bool(value):
                cmd.append(flag)
            continue
        cmd.extend([flag, str(caster(value))])

    job_id = uuid.uuid4().hex
    job = JobInfo(
        id=job_id,
        name=name,
        command=cmd,
        cwd=cwd,
        created_at=_now_iso(),
        status="queued",
    )

    logs_dir = _jobs_dir()
    log_path = str((logs_dir / f"{job_id}.log").resolve())
    job.log_path = log_path

    with _LOCK:
        _JOBS[job_id] = job

    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True)
    t.start()
    return job


def _run_job(job_id: str) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = _now_iso()

    try:
        job = get_job(job_id)
        if job is None:
            return

        # Make sure CWD exists.
        cwd = job.cwd
        if not os.path.isdir(cwd):
            raise RuntimeError(f"Job cwd does not exist: {cwd}")

        log_path = job.log_path or str((_jobs_dir() / f"{job_id}.log").resolve())
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, "ab", buffering=0) as f:
            f.write(f"[{_now_iso()}] START {job.name}: {' '.join(job.command)}\n".encode("utf-8"))
            proc = subprocess.Popen(
                job.command,
                cwd=cwd,
                stdout=f,
                stderr=subprocess.STDOUT,
                env=dict(os.environ),
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
            f.write(f"[{_now_iso()}] END {job.name} rc={rc}\n".encode("utf-8"))
    except Exception as exc:
        with _LOCK:
            j = _JOBS.get(job_id)
            if j:
                j.returncode = -1
                j.finished_at = _now_iso()
                j.status = "failed"
        try:
            log_path = get_job(job_id).log_path if get_job(job_id) else None
            if log_path:
                with open(log_path, "ab", buffering=0) as f:
                    f.write(f"[{_now_iso()}] ERROR {exc!r}\n".encode("utf-8"))
        except Exception:
            pass


def job_to_dict(job: JobInfo) -> dict[str, Any]:
    data = asdict(job)
    return data


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
    # If we started mid-line, drop the partial first line for readability.
    if start > 0:
        nl = data.find(b"\n")
        if nl != -1:
            data = data[nl + 1 :]
    return data.decode("utf-8", errors="replace")

