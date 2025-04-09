
import json
from datetime import datetime
import os
from typing import Optional, Dict, Any

FAULT_LOG_PATH = 'faults.json'

def log_fault(message: str, details: Optional[Dict[str, Any]] = None, source: str = 'system') -> bool:
    try:
        fault = {
            'timestamp': datetime.utcnow().isoformat(),
            'message': message,
            'source': source,
            'details': details or {},
            'batch_id': details.get('batch_id') if details else None,
            'status': 'NEW'
        }

        faults = []
        if os.path.exists(FAULT_LOG_PATH):
            try:
                with open(FAULT_LOG_PATH, 'r') as f:
                    faults = json.load(f)
            except json.JSONDecodeError:
                faults = []

        faults.append(fault)

        with open(FAULT_LOG_PATH, 'w') as f:
            json.dump(faults, f, indent=2)
        return True
    except Exception as e:
        print(f"Error logging fault: {str(e)}")
        return False
