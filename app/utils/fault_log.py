"""Structured fault-log persistence helpers.

Synopsis:
Record operational faults to a JSON log file with timestamps, source metadata,
and optional details so troubleshooting data survives request boundaries.

Glossary:
- Fault record: Structured dictionary describing one logged failure condition.
- Fault log path: Filesystem destination for persisted fault history.
- Triage status: Workflow state assigned to newly logged fault entries.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .json_store import read_json_file, write_json_file
from .timezone_utils import TimezoneUtils

LOG = logging.getLogger(__name__)
DEFAULT_FAULT_LOG = Path(os.environ.get("FAULT_LOG_PATH", "faults.json"))


def log_fault(
    message: str,
    details: Optional[Dict[str, Any]] = None,
    source: str = "system",
    *,
    log_path: Path = DEFAULT_FAULT_LOG,
) -> bool:
    """Persist a structured fault entry for later triage."""
    fault_record = {
        "timestamp": TimezoneUtils.utc_now().isoformat(),
        "message": message,
        "source": source,
        "details": details or {},
        "batch_id": (details or {}).get("batch_id"),
        "status": "NEW",
    }

    try:
        existing = read_json_file(log_path, default=[]) or []
    except Exception as err:  # pragma: no cover - defensive path
        LOG.warning("Failed to read fault log; starting new file: %s", err)
        existing = []

    existing.append(fault_record)

    try:
        write_json_file(log_path, existing)
        return True
    except Exception as err:
        LOG.error("Failed to write fault log %s: %s", log_path, err)
        return False
