# Base-36 FIFO ID Generator
# Replaces integer auto-increment with structured base-36 codes

BASE36_CHARS = '0123456789abcdefghijklmnopqrstuvwxyz'

def get_change_type_prefix(change_type):
    """Get 3-letter prefix for change type"""
    prefix_map = {
        'restock': 'RSK',
        'batch': 'BTC', 
        'spoil': 'SPL',
        'trash': 'TRS',
        'recount': 'RCN',
        'finished_batch': 'FIN',
        'refunded': 'REF',
        'cost_override': 'CST'
    }
    return prefix_map.get(change_type, 'UNK')

def int_to_base36(number):
    """Convert integer to base-36 string"""
    if number == 0:
        return '0'

    result = ''
    base = len(BASE36_CHARS)  # Now 36 characters
    while number > 0:
        result = BASE36_CHARS[number % base] + result
        number //= base
    return result

def generate_fifo_id(change_type):
    """Generate next FIFO ID for given change type"""
    from models import db, InventoryHistory

    prefix = get_change_type_prefix(change_type)

    # Get the highest sequence number across all prefixes
    # This ensures global uniqueness across all change types
    latest_entry = db.session.query(InventoryHistory.id).order_by(InventoryHistory.id.desc()).first()

    if latest_entry:
        next_sequence = latest_entry[0] + 1
    else:
        next_sequence = 1

    # Convert to base-36 first
    base36_raw = int_to_base36(next_sequence)
    print(f"DEBUG: Raw base-36 conversion {next_sequence} -> '{base36_raw}' (length: {len(base36_raw)})")

    # Apply padding
    sequence_base36 = base36_raw.zfill(6)  # Pad to 6 characters
    print(f"DEBUG: After zfill(6): '{sequence_base36}' (length: {len(sequence_base36)})")

    full_fifo_id = f"{prefix}-{sequence_base36}"
    print(f"DEBUG: Full FIFO ID: '{full_fifo_id}' (total length: {len(full_fifo_id)})")
    print(f"DEBUG: Characters in sequence: {[char for char in sequence_base36]}")

    return full_fifo_id

def base36_to_int(base36_str):
    """Convert base-36 string back to integer"""
    result = 0
    base = len(BASE36_CHARS)  # 36 characters
    for char in base36_str:
        result = result * base + BASE36_CHARS.index(char)
    return result

def validate_fifo_id(fifo_id):
    """Validate FIFO ID format"""
    if not fifo_id or '-' not in fifo_id:
        return False

    parts = fifo_id.split('-')
    if len(parts) != 2:
        return False

    prefix, sequence = parts

    # Check if all characters in sequence are valid base-36
    try:
        for char in sequence:
            if char not in BASE36_CHARS:
                return False
        return True
    except:
        return False
import base64
import time

def generate_fifo_code(prefix):
    """Generates a base-32 encoded FIFO code with a prefix."""
    timestamp = int(time.time() * 1000)  # Millisecond precision
    encoded_timestamp = base64.b32encode(str(timestamp).encode()).decode('utf-8').lower()
    return f"{prefix[:3].upper()}-{encoded_timestamp}"  # Use first 3 chars of prefix
