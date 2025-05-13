
from models import InventoryItem

def check_container_availability(container_ids, scale=1.0):
    """Check if requested containers are available in inventory"""
    results = []
    all_ok = True
    
    for container_id in container_ids:
        container = InventoryItem.query.get(container_id)
        if not container:
            continue
            
        needed_amount = scale  # One container per batch by default
        available = container.quantity or 0
        
        if available >= needed_amount:
            status = 'OK'
        elif available >= needed_amount * 0.5:
            status = 'LOW'
            all_ok = False
        else:
            status = 'NEEDED'
            all_ok = False
            
        results.append({
            'type': 'container',
            'name': container.name,
            'needed': needed_amount,
            'available': available,
            'unit': container.unit,
            'status': status
        })
        
    return results, all_ok
