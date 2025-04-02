import json
import os
import qrcode
from flask import request
import json
from pathlib import Path

def load_categories():
    path = Path("categories.json")
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "product_types": [],
        "use_areas": [],
        "primary_ingredients": [],
        "use_cases": []
    }

DATA_FILE = 'data.json'

def load_data():
    default_data = {
        "ingredients": [],
        "recipes": [],
        "batches": [],
        "recipe_counter": 0,
        "batch_counter": 0,
        "products": [],
        "product_events": [],
        "inventory_log": []
    }
    
    try:
        if not os.path.exists(DATA_FILE):
            save_data(default_data)
            return default_data
            
        with open(DATA_FILE, 'r') as f:
            content = f.read().strip()
            if not content:  # Handle empty file
                save_data(default_data)
                return default_data
                
            data = json.loads(content)
            # Clean up any empty quantities
            if 'ingredients' in data:
                for ing in data['ingredients']:
                    if ing.get('quantity') == '':
                        ing['quantity'] = 0
                
            data = json.loads(content)
            # Ensure all required keys exist
            for key in default_data:
                data.setdefault(key, default_data[key])
            return data
            
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading data: {str(e)}")
        # Backup corrupted file if it exists
        if os.path.exists(DATA_FILE):
            backup_name = f"{DATA_FILE}.backup"
            try:
                os.rename(DATA_FILE, backup_name)
                print(f"Corrupted data file backed up to {backup_name}")
            except:
                pass
        # Return fresh data structure
        save_data(default_data)
        return default_data

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def generate_qr_for_batch(batch_id):
    from urllib.parse import quote
    safe_batch_id = quote(str(batch_id))
    url = f"{request.host_url}feedback/{safe_batch_id}"
    img = qrcode.make(url)
    os.makedirs('static/qr', exist_ok=True)
    img_path = f"static/qr/{batch_id}.png"
    img.save(img_path)
    return img_path