
import json

def get_setting(key, default=None):
    try:
        with open("settings.json", "r") as f:
            data = json.load(f)
        return data.get(key, default)
    except:
        return default
