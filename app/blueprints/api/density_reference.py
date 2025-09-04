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
        # Load density reference data - go up to project root
        # Current file is at: app/blueprints/api/density_reference.py
        # We need to go up 4 levels to reach project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        density_file_path = os.path.join(project_root, 'data', 'density_reference.json')

        # Load density data from JSON file - no fallback
        if not os.path.exists(density_file_path):
            return jsonify({'error': f'Density reference file not found at {density_file_path}'}), 500
            
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