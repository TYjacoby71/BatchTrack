import os
import json
from flask import Blueprint, render_template, jsonify
from app.models import GlobalItem, IngredientCategory
from flask_login import login_required
from app.services.density_assignment_service import DensityAssignmentService
from sqlalchemy import func

density_reference_bp = Blueprint('density_reference', __name__)

@density_reference_bp.route('/density-reference/options')
@login_required
def get_density_options():
    """Get all density options (DB-backed) for the search modal"""
    try:
        # Build categories from GlobalItem.reference_category
        categories = {}
        # Only ingredient-type global items participate in density reference
        items = GlobalItem.query.filter_by(item_type='ingredient').all()
        for gi in items:
            cat = gi.reference_category or 'Other'
            if cat not in categories:
                categories[cat] = {
                    'name': cat,
                    'items': [],
                    'default_density': None
                }
            categories[cat]['items'].append({
                'name': gi.name,
                'density_g_per_ml': gi.density,
                'aliases': gi.aka_names or []
            })

        # Compute default density per category (average of defined densities)
        for cat_data in categories.values():
            densities = [i['density_g_per_ml'] for i in cat_data['items'] if isinstance(i['density_g_per_ml'], (int, float)) and i['density_g_per_ml'] > 0]
            if densities:
                cat_data['default_density'] = sum(densities) / len(densities)
            else:
                cat_data['default_density'] = None

        # Return compact payload compatible with existing modal consumption
        return jsonify(list(categories.values()))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@density_reference_bp.route('/density-reference')
@density_reference_bp.route('/api/density-reference')
def get_density_reference():
    """Serve density reference page from database (no JSON dependency)"""
    try:
        # Build categories from GlobalItem
        categories = {}
        items = GlobalItem.query.filter_by(item_type='ingredient').all()
        for gi in items:
            cat = gi.reference_category or 'Other'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                'name': gi.name,
                'density_g_per_ml': gi.density or 0.0,
                'aliases': gi.aka_names or [],
                'notes': None
            })

        # Sort categories and items
        for cat_name in categories:
            categories[cat_name].sort(key=lambda x: x['name'])

        return render_template('density_reference.html', categories=categories, density_data={'source': 'database'})
    except Exception as e:
        return f"<h1>Error loading density reference</h1><p>{str(e)}</p>", 500