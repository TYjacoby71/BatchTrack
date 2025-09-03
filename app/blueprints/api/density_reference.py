from flask import Blueprint, jsonify, render_template_string
from flask_login import login_required
import json
import os

density_reference_bp = Blueprint('density_reference', __name__)

@density_reference_bp.route('/api/density-reference')
@login_required 
def get_density_reference():
    """Serve density reference data as a formatted page"""
    try:
        # Load density reference data
        density_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'density_reference.json')

        with open(density_file_path, 'r') as f:
            density_data = json.load(f)

        # Create a simple HTML page for the density reference
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Ingredient Density Reference</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { padding: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .category-section { margin-bottom: 2rem; }
        .density-item { padding: 0.5rem 0; border-bottom: 1px solid #eee; }
        .density-value { font-weight: bold; color: #0d6efd; }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2><i class="fas fa-balance-scale text-primary"></i> Ingredient Density Reference</h2>
            <small class="text-muted">Densities in grams per milliliter (g/ml)</small>
        </div>

        <div class="alert alert-info">
            <i class="fas fa-info-circle"></i>
        
except Exception as e:
        return jsonify({'error': f'Failed to load density reference: {str(e)}'}), 500