
import string
from models import InventoryHistory, db

# Base-32 character set (excluding ambiguous characters)
BASE32_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def get_change_type_prefix(change_type):
    """Map change types to prefixes"""
    prefix_map = {
        'restock': 'RSK',
        'batch': 'BTC', 
        'spoil': 'SPL',
        'trash': 'TRS',
        'recount': 'RCN',
        'refunded': 'RFD',
        'adjustment': 'ADJ'
    }
    return prefix_map.get(change_type, 'UNK')

def int_to_base32(number):
    """Convert integer to base-32 string"""
    if number == 0:
        return BASE32_CHARS[0]
    
    result = ""
    while number > 0:
        result = BASE32_CHARS[number % 32] + result
        number //= 32
    return result

def generate_fifo_code(change_type):
    """Generate next FIFO code for given change type"""
    prefix = get_change_type_prefix(change_type)
    
    # Get the highest sequence number for this prefix
    existing_codes = db.session.query(InventoryHistory.fifo_code).filter(
        InventoryHistory.fifo_code.like(f'{prefix}-%')
    ).all()
    
    max_sequence = 0
    for (code,) in existing_codes:
        if code and '-' in code:
            try:
                sequence_part = code.split('-')[1]
                # Convert base-32 back to integer to find max
                sequence_num = base32_to_int(sequence_part)
                max_sequence = max(max_sequence, sequence_num)
            except (ValueError, IndexError):
                continue
    
    next_sequence = max_sequence + 1
    sequence_base32 = int_to_base32(next_sequence).zfill(5)  # Pad to 5 characters
    
    return f"{prefix}-{sequence_base32}"

def base32_to_int(base32_str):
    """Convert base-32 string back to integer"""
    result = 0
    for char in base32_str:
        result = result * 32 + BASE32_CHARS.index(char)
    return result

def validate_fifo_code(fifo_code):
    """Validate FIFO code format"""
    if not fifo_code or '-' not in fifo_code:
        return False
    
    parts = fifo_code.split('-')
    if len(parts) != 2:
        return False
    
    prefix, sequence = parts
    
    # Check if all characters in sequence are valid base-32
    try:
        for char in sequence:
            if char not in BASE32_CHARS:
                return False
        return True
    except:
        return False
