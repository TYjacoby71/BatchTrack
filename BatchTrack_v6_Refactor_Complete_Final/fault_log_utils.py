
import json
from datetime import datetime
import os

FAULT_LOG_PATH = 'faults.json'

def log_fault(message, details=None, source='system'):
    fault = {
        'timestamp': datetime.utcnow().isoformat(),
        'message': message,
        'source': source,
        'details': details or {}
    }

    faults = []
    if os.path.exists(FAULT_LOG_PATH):
        with open(FAULT_LOG_PATH, 'r') as f:
            try:
                faults = json.load(f)
            except json.JSONDecodeError:
                faults = []

    faults.append(fault)

    with open(FAULT_LOG_PATH, 'w') as f:
        json.dump(faults, f, indent=2)
