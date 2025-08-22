import secrets
import time
import random

BASE36_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def int_to_base36(num):
    """Convert integer to base36 string"""
    if num == 0:
        return '0'

    digits = []
    while num:
        num, remainder = divmod(num, 36)
        digits.append(BASE36_CHARS[remainder])

    return ''.join(reversed(digits))

def generate_fifo_code(change_type, item_id=None, is_lot_creation=False):
    """
    Generate FIFO tracking code with appropriate prefix

    Args:
        change_type: Type of inventory change
        item_id: Item ID (for uniqueness)
        is_lot_creation: True if creating an InventoryLot, False for events

    Returns:
        String: FIFO code (e.g., 'LOT-A7B2C3D4' or 'RCN-X9Y8Z7W6')
    """

    # Determine prefix based on operation type
    if is_lot_creation:
        prefix = 'LOT'  # All lot creations use LOT prefix
    else:
        # Event codes - map change types to prefixes
        event_prefixes = {
            'recount': 'RCN',
            'sale': 'SLD',
            'use': 'USE',
            'spoil': 'SPL',
            'trash': 'TRS',
            'expired': 'EXP',
            'damaged': 'DMG',
            'quality_fail': 'QFL',
            'batch': 'BCH',
            'sample': 'SMP',
            'tester': 'TST',
            'gift': 'GFT',
            'returned': 'RTN',
            'refunded': 'REF',
            'cost_override': 'CST'
        }
        prefix = event_prefixes.get(change_type, 'TXN')

    # Generate unique suffix using timestamp + item_id + random
    timestamp_component = int_to_base36(int(time.time() * 1000) % 1000000)[:4]
    item_component = int_to_base36((item_id or 1) % 1000)[:2]
    random_component = int_to_base36(random.randint(100, 999))[:2]

    suffix = f"{timestamp_component}{item_component}{random_component}".upper()

    return f"{prefix}-{suffix}"

def parse_fifo_code(fifo_code):
    """
    Parse FIFO code to extract prefix and suffix

    Returns:
        dict: {'prefix': str, 'suffix': str, 'is_lot': bool}
    """
    if not fifo_code or '-' not in fifo_code:
        return {'prefix': None, 'suffix': None, 'is_lot': False}

    parts = fifo_code.split('-', 1)
    prefix = parts[0]
    suffix = parts[1] if len(parts) > 1 else ''

    return {
        'prefix': prefix,
        'suffix': suffix,
        'is_lot': prefix == 'LOT'
    }

def validate_fifo_code(fifo_code):
    """Validate FIFO code format"""
    parsed = parse_fifo_code(fifo_code)
    if not parsed['prefix']:
        return False

    valid_prefixes = [
        'LOT', 'RCN', 'SLD', 'USE', 'SPL', 'TRS', 'EXP', 'DMG',
        'QFL', 'BCH', 'SMP', 'TST', 'GFT', 'RTN', 'REF', 'CST', 'TXN'
    ]

    return parsed['prefix'] in valid_prefixes

# Legacy compatibility
def generate_fifo_id(change_type):
    """Legacy function - use generate_fifo_code instead"""
    return generate_fifo_code(change_type)