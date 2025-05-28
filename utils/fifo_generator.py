# Base-32 FIFO ID Generator
# Replaces integer auto-increment with structured base-32 codes

BASE32_CHARS = '0123456789abcdefghijklmnopqrstuvwxyz'

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

def int_to_base32(number):
    """Convert integer to base-36 string"""
    if number == 0:
        return '0'

    result = ''
    base = len(BASE32_CHARS)  # Now 36 characters
    while number > 0:
        result = BASE32_CHARS[number % base] + result
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

    sequence_base32 = int_to_base32(next_sequence).zfill(6)  # Pad to 6 characters

    return f"{prefix}-{sequence_base32}"

def base32_to_int(base32_str):
    """Convert base-36 string back to integer"""
    result = 0
    base = len(BASE32_CHARS)  # Now 36 characters
    for char in base32_str:
        result = result * base + BASE32_CHARS.index(char)
    return result

def validate_fifo_id(fifo_id):
    """Validate FIFO ID format"""
    if not fifo_id or '-' not in fifo_id:
        return False

    parts = fifo_id.split('-')
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