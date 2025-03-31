
import json
import os
import qrcode
from flask import request

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
    url = f"{request.host_url}feedback/{batch_id}"
    img = qrcode.make(url)
    os.makedirs('static/qr', exist_ok=True)
    img_path = f"static/qr/{batch_id}.png"
    img.save(img_path)
    return img_path
