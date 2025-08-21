# Base-32 FIFO ID Generator
# Generates structured base-32 codes for FIFO tracking

import secrets
import base64
from datetime import datetime
import time
import random
from typing import Dict

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
        String: FIFO code (e.g., 'LOT-A7B2C3D4' or 'RCN-X9Y8Z7W6')
    """

    # If from batch and has batch label, use batch label
    if batch_label:
        return f"BCH-{batch_label}"

    # For recount operations, use enhanced logic
    if change_type == 'recount':
        if remaining_quantity > 0:
            prefix = 'LOT'  # Recount overflow creates new lots
        else:
            prefix = 'RCN'  # Recount refills/deductions don't create lots
    else:
        # Determine if this is a lot (creates remaining quantity)
        # Only these types with positive quantities create lots
        lot_creation_types = [
            'restock', 
            'finished_batch', 
            'manual_addition',
            'initial_stock'
        ]

        is_lot = change_type in lot_creation_types and remaining_quantity > 0

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
    """Map change types to their FIFO code prefixes"""
    prefix_map = {
        # Additive operations - create new lots
        'restock': 'LOT',
        'manual_addition': 'LOT',
        'returned': 'RTN',
        'refunded': 'RFD',
        'finished_batch': 'BCH',
        'initial_stock': 'LOT',

        # Deductive operations - consume from lots
        'use': 'USE',
        'sale': 'SLD',
        'spoil': 'SPL',
        'trash': 'TRS',
        'expired': 'EXP',
        'damaged': 'DMG',
        'quality_fail': 'QFL',
        'sample': 'SMP',
        'tester': 'TST',
        'gift': 'GFT',
        'reserved': 'RSV',
        'batch': 'BCH',

        # Special operations
        'recount': 'RCN',  # Default for recount (deductive)
        'cost_override': 'CST',
        'unit_conversion': 'CNV',
    }
    return prefix_map.get(change_type, 'UNK')

def get_fifo_prefix(change_type, has_remaining_quantity):
    """
    Enhanced FIFO prefix logic that considers remaining quantity.
    For recount operations:
    - If has_remaining_quantity > 0: Use LOT prefix (overflow case)
    - If has_remaining_quantity = 0: Use RCN prefix (deductive case)
    """
    if change_type == 'recount':
        if has_remaining_quantity:
            return 'LOT'  # Recount overflow creates a new lot
        else:
            return 'RCN'  # Recount deduction consumes existing lots

    # For all other change types, use the standard mapping
    return get_change_type_prefix(change_type)

# Legacy function for backward compatibility
def generate_fifo_id(change_type):
    """Legacy function - use generate_fifo_code instead"""
    return generate_fifo_code(change_type)

def generate_fifo_code(change_type: str, item_id: int, remaining_quantity: float = 0.0) -> str:
    """Generate unique FIFO tracking code"""
    prefix = get_change_type_prefix(change_type)
    
    # For lot-creating operations (restock, finished_batch, manual_addition), use LOT prefix
    if change_type in ['restock', 'finished_batch', 'manual_addition', 'initial_stock'] and remaining_quantity > 0:
        prefix = 'LOT'
    
    # Use higher precision timestamp + random component for uniqueness
    timestamp_ms = int(time.time() * 1000000)  # microseconds for better uniqueness
    timestamp_component = int_to_base36(timestamp_ms % 100000000)  # larger range
    item_component = int_to_base36(item_id % 10000)  # larger item range
    random_component = int_to_base36(random.randint(100, 999))  # add randomness
    return f"{prefix}{timestamp_component}{item_component}{random_component}"