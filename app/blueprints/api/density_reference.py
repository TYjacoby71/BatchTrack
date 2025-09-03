from flask import Blueprint, jsonify, render_template
from flask_login import login_required
import json
import os

density_reference_bp = Blueprint('density_reference', __name__)

@density_reference_bp.route('/')
@login_required
def get_density_reference():
    """Serve density reference data as a formatted page"""
    try:
        # Load density reference data
        density_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'density_reference.json')

        # Fallback to minimal data if file doesn't exist, as per original logic
        if not os.path.exists(density_file_path):
            density_data = {
                'common_densities': [
                    {'name': 'Water', 'density_g_per_ml': 1.0, 'category': 'Liquids', 'aliases': ['H2O']},
                    {'name': 'Olive Oil', 'density_g_per_ml': 0.92, 'category': 'Oils', 'aliases': ['EVOO']},
                    {'name': 'All-Purpose Flour', 'density_g_per_ml': 0.6, 'category': 'Flours', 'aliases': ['AP flour']},
                    {'name': 'White Sugar', 'density_g_per_ml': 0.85, 'category': 'Sugars', 'aliases': ['granulated sugar']},
                    {'name': 'Table Salt', 'density_g_per_ml': 2.16, 'category': 'Salts', 'aliases': ['sodium chloride']},
                    {'name': 'Honey', 'density_g_per_ml': 1.4, 'category': 'Syrups', 'aliases': ['raw honey']},
                    {'name': 'Butter', 'density_g_per_ml': 0.91, 'category': 'Fats', 'aliases': ['unsalted butter']},
                    {'name': 'Whole Milk', 'density_g_per_ml': 1.03, 'category': 'Dairy', 'aliases': ['milk']},
                ]
            }
        else:
            with open(density_file_path, 'r') as f:
                density_data = json.load(f)

        # Group densities by category
        categories = {}
        for item in density_data.get('common_densities', []):
            category = item.get('category', 'Other')
            if category not in categories:
                categories[category] = []
            categories[category].append(item)

        # Sort categories and items within each category
        for category in categories:
            categories[category].sort(key=lambda x: x['name'])

        return render_template('density_reference.html', categories=categories, density_data=density_data)

    except Exception as e:
        return jsonify({'error': f'Failed to load density reference: {str(e)}'}), 500