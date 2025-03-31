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
    if not os.path.exists(DATA_FILE):
        return {"ingredients": [], "recipes": [], "batches": [], "recipe_counter": 0, "batch_counter": 0}
    with open(DATA_FILE, 'r') as f:
        data = json.load(f)
        data.setdefault("ingredients", [])
        data.setdefault("recipes", [])
        data.setdefault("batches", [])
        data.setdefault("recipe_counter", len(data["recipes"]))
        data.setdefault("batch_counter", len(data["batches"]))
        return data

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