from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.json_store import read_json_file, write_json_file
from app.utils.timezone_utils import TimezoneUtils

LOG = logging.getLogger(__name__)
FAULT_LOG_FILENAME = os.environ.get("FAULT_LOG_PATH", "faults.json")
FAULT_LOG_PATH = Path(FAULT_LOG_FILENAME)


def log_fault(
    message: str,
    details: Optional[Dict[str, Any]] = None,
    source: str = "system",
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
        existing = read_json_file(str(FAULT_LOG_PATH), default=[]) or []
    except Exception as err:  # pragma: no cover - defensive path
        LOG.warning("Failed to read fault log; starting new file: %s", err)
        existing = []

    existing.append(fault_record)

    try:
        write_json_file(str(FAULT_LOG_PATH), existing)
        return True
    except Exception as err:
        LOG.error("Failed to write fault log %s: %s", FAULT_LOG_PATH, err)
        return False
