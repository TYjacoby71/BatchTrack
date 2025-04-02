
from datetime import datetime
import json
from app.routes.utils import load_data, save_data

def log_fault(message, details):
    """Log a fault with message and details to the data store"""
    data = load_data()
    if "faults" not in data:
        data["faults"] = []
        
    fault = {
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "details": details
    }
    
    data["faults"].append(fault)
    save_data(data)
