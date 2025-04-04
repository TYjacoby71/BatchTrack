
from flask import Blueprint, jsonify
from app.routes.utils import load_data

start_flow_bp = Blueprint('start_flow', __name__)

@start_flow_bp.route('/recipes.json')
def recipes_json():
    data = load_data()
    return jsonify({"recipes": data.get('recipes', [])})
