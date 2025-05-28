# Base-32 FIFO ID Generator
# Replaces integer auto-increment with structured base-32 codes

BASE32_CHARS = '0123456789abcdefghijklmnopqrstuv'

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

def int_to_mixed_alphanumeric(number):
    """Convert integer to mixed alphanumeric format: letters first, then numbers (AA000)"""
    if number == 0:
        return 'AA000'
    
    # Convert to base-26 for letters (A-Z) and base-10 for numbers
    # Format: 2 letters + 3 numbers
    
    # Calculate letter part (base-26: A=0, B=1, ..., Z=25)
    letter_part = number // 1000  # First divide by 1000 to get letter portion
    number_part = number % 1000   # Remainder becomes the number portion
    
    # Convert letter part to two letters
    first_letter = chr(ord('A') + (letter_part // 26) % 26)
    second_letter = chr(ord('A') + letter_part % 26)
    
    # Format as AA000
    return f"{first_letter}{second_letter}{number_part:03d}"

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

    sequence_mixed = int_to_mixed_alphanumeric(next_sequence)

    return f"{prefix}-{sequence_mixed}"

def mixed_alphanumeric_to_int(mixed_str):
    """Convert mixed alphanumeric string back to integer (AA000 format)"""
    if len(mixed_str) != 5:
        return 0
    
    # Extract letters and numbers
    first_letter = ord(mixed_str[0]) - ord('A')
    second_letter = ord(mixed_str[1]) - ord('A')
    number_part = int(mixed_str[2:5])
    
    # Reconstruct original number
    letter_part = first_letter * 26 + second_letter
    return letter_part * 1000 + number_part

def validate_fifo_id(fifo_id):
    """Validate FIFO ID format (PREFIX-AA000)"""
    if not fifo_id or '-' not in fifo_id:
        return False

    parts = fifo_id.split('-')
    if len(parts) != 2:
        return False

    prefix, sequence = parts

    # Check format: 2 letters + 3 numbers
    if len(sequence) != 5:
        return False
    
    try:
        # First two characters should be letters A-Z
        if not (sequence[0].isalpha() and sequence[1].isalpha()):
            return False
        # Last three characters should be digits
        if not sequence[2:].isdigit():
            return False
        return True
    except:
        return False