
# Base-32 FIFO ID Generator
# Generates structured base-32 codes for FIFO tracking

import secrets
import base64
from datetime import datetime

BASE36_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def get_fifo_prefix(change_type, is_lot=False):
    """
    Get 3-letter prefix for FIFO code
    - LOT: Events that create remaining quantity (restock, finished_batch, etc.)
    - Action prefixes: Events that consume or adjust quantity
    """
    if is_lot:
        return 'LOT'
    
    prefix_map = {
        'sold': 'SLD',
        'shipped': 'SHP', 
        'spoil': 'SPL',
        'trash': 'TRS',
        'damaged': 'DMG',
        'expired_disposal': 'EXP',
        'used': 'USE',
        'batch': 'BCH',
        'recount': 'RCN',
        'refunded': 'REF',
        'returned': 'RTN',
        'cost_override': 'CST',
        'manual_addition': 'ADD',
        'tester': 'TST',
        'gift': 'GFT',
        'quality_fail': 'QFL'
    }
    return prefix_map.get(change_type, 'TXN')

def generate_fifo_code(change_type, remaining_quantity=0, batch_label=None):
    """
    Generate FIFO code with proper prefix and base32 suffix
    
    Args:
        change_type: Type of inventory change
        remaining_quantity: Quantity remaining after transaction (>0 = lot)
        batch_label: If from batch, use batch label instead of generated code
    
    Returns:
        String: FIFO code (e.g., 'LOT-A7B2C3D4' or 'SLD-X9Y8Z7W6')
    """
    
    # If from batch and has batch label, use batch label
    if batch_label:
        return f"BCH-{batch_label}"
    
    # Determine if this is a lot (creates remaining quantity)
    is_lot = remaining_quantity > 0 and change_type in [
        'restock', 'finished_batch', 'manual_addition', 'returned', 'refunded'
    ]
    
    # Get prefix
    prefix = get_fifo_prefix(change_type, is_lot)
    
    # Generate base36 suffix (8 characters)
    suffix = int_to_base36(secrets.randbits(32))[:8].upper()
    
    return f"{prefix}-{suffix}"

def generate_batch_fifo_code(batch_label, change_type='finished_batch'):
    """Generate FIFO code for batch-related transactions"""
    return f"BCH-{batch_label}"

def parse_fifo_code(fifo_code):
    """
    Parse FIFO code to extract prefix and suffix
    
    Returns:
        dict: {'prefix': str, 'suffix': str, 'is_lot': bool, 'is_batch': bool}
    """
    if not fifo_code or '-' not in fifo_code:
        return {'prefix': None, 'suffix': None, 'is_lot': False, 'is_batch': False}
    
    parts = fifo_code.split('-', 1)
    prefix = parts[0]
    suffix = parts[1] if len(parts) > 1 else ''
    
    return {
        'prefix': prefix,
        'suffix': suffix,
        'is_lot': prefix == 'LOT',
        'is_batch': prefix == 'BCH'
    }

def validate_fifo_code(fifo_code):
    """Validate FIFO code format"""
    parsed = parse_fifo_code(fifo_code)
    if not parsed['prefix']:
        return False
    
    # Check if prefix is valid
    valid_prefixes = ['LOT', 'SLD', 'SHP', 'SPL', 'TRS', 'DMG', 'EXP', 'USE', 
                     'BCH', 'RCN', 'REF', 'RTN', 'CST', 'ADD', 'TST', 'GFT', 'QFL', 'TXN']
    
    if parsed['prefix'] not in valid_prefixes:
        return False
    
    # For batch codes, suffix can be anything
    if parsed['is_batch']:
        return True
    
    # For other codes, check base36 format
    try:
        if parsed['suffix']:
            # Check if all characters are valid base36
            for char in parsed['suffix']:
                if char not in BASE36_CHARS:
                    return False
        return True
    except:
        return False

def int_to_base36(num):
    """Convert integer to base36 string"""
    if num == 0:
        return '0'
    
    digits = []
    while num:
        num, remainder = divmod(num, 36)
        digits.append(BASE36_CHARS[remainder])
    
    return ''.join(reversed(digits))

def base36_to_int(base36_str):
    """Convert base36 string to integer"""
    return int(base36_str, 36)

def get_change_type_prefix(change_type):
    """Legacy function - use get_fifo_prefix instead"""
    return get_fifo_prefix(change_type, False)

# Legacy function for backward compatibility
def generate_fifo_id(change_type):
    """Legacy function - use generate_fifo_code instead"""
    return generate_fifo_code(change_type)
