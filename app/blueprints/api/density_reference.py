
import os
import json
from flask import Blueprint, jsonify, render_template
from flask_login import login_required
from app.services.density_assignment_service import DensityAssignmentService

density_reference_bp = Blueprint('density_reference', __name__)

@density_reference_bp.route('/density-reference/options')
@login_required  
def get_density_options():
    """Get all density options for the search modal"""
    try:
        from flask_login import current_user
        org_id = current_user.organization_id if current_user.organization_id else 0
        options = DensityAssignmentService.get_category_options(org_id)  # Reference data is not org-specific
        return jsonify(options)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@density_reference_bp.route('/density-reference')
@density_reference_bp.route('/api/density-reference')
def get_density_reference():
    """Serve density reference data as a formatted page"""
    try:
        # Load density reference data - go up to project root
        # Current file is at: app/blueprints/api/density_reference.py
        # We need to go up 4 levels to reach project root (app/blueprints/api/density_reference.py -> /)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        density_file_path = os.path.join(project_root, 'data', 'density_reference.json')

        print(f"Looking for density file at: {density_file_path}")
        print(f"File exists: {os.path.exists(density_file_path)}")

        # Load density data from JSON file - no fallback
        if not os.path.exists(density_file_path):
            return f"<h1>Error: Density reference file not found</h1><p>Expected at: {density_file_path}</p>", 404
            
        with open(density_file_path, 'r') as f:
            density_data = json.load(f)

        print(f"Loaded density data with {len(density_data.get('common_densities', []))} items")

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

        print(f"Grouped into {len(categories)} categories: {list(categories.keys())}")

        return render_template('density_reference.html', categories=categories, density_data=density_data)

    except Exception as e:
        return f"<h1>Error loading density reference</h1><p>{str(e)}</p>", 500
