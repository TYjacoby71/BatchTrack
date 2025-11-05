
import os
from typing import Optional, Dict, Any

from app.utils.timezone_utils import TimezoneUtils
from app.utils.json_store import read_json_file, write_json_file

FAULT_LOG_PATH = 'faults.json'

def log_fault(message: str, details: Optional[Dict[str, Any]] = None, source: str = 'system') -> bool:
    try:
        fault = {
            'timestamp': TimezoneUtils.utc_now().isoformat(),
            'message': message,
            'source': source,
            'details': details or {},
            'batch_id': details.get('batch_id') if details else None,
            'status': 'NEW'
        }

        faults = read_json_file(FAULT_LOG_PATH, default=[]) or []

        faults.append(fault)

        write_json_file(FAULT_LOG_PATH, faults)
        return True
    except Exception as e:
        print(f"Error logging fault: {str(e)}")
        return False
