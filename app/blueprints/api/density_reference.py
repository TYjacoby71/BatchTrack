
from flask import Blueprint, jsonify, render_template_string
from flask_login import login_required
import json
import os

density_reference_bp = Blueprint('density_reference', __name__)

@density_reference_bp.route('/')
@login_required
def get_density_reference():
    """Serve density reference data as a formatted page with search"""
    try:
        # Load density reference data
        density_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'density_reference.json')
        
        if not os.path.exists(density_file_path):
            # Fallback minimal data
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

        # Create HTML template with search functionality
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Ingredient Density Reference</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { 
            padding: 20px; 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background-color: #f8f9fa;
        }
        .reference-container {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            padding: 2rem;
            max-height: 80vh;
            overflow-y: auto;
        }
        .search-container {
            position: sticky;
            top: 0;
            background: white;
            z-index: 10;
            padding-bottom: 1rem;
            margin-bottom: 1rem;
            border-bottom: 2px solid #e9ecef;
        }
        .search-input {
            border: 2px solid #dee2e6;
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 16px;
            transition: border-color 0.3s ease;
        }
        .search-input:focus {
            border-color: #0d6efd;
            box-shadow: 0 0 0 0.2rem rgba(13, 110, 253, 0.25);
        }
        .category-section { 
            margin-bottom: 2rem; 
            border: 1px solid #e9ecef;
            border-radius: 8px;
            overflow: hidden;
        }
        .category-header {
            background: linear-gradient(135deg, #0d6efd, #6610f2);
            color: white;
            padding: 1rem;
            margin: 0;
            font-weight: 600;
        }
        .category-content {
            padding: 1rem;
        }
        .density-item { 
            padding: 0.75rem;
            border-bottom: 1px solid #f8f9fa;
            border-radius: 6px;
            margin-bottom: 0.5rem;
            transition: background-color 0.2s ease;
        }
        .density-item:hover {
            background-color: #f8f9fa;
        }
        .density-item:last-child {
            border-bottom: none;
            margin-bottom: 0;
        }
        .density-value { 
            font-weight: bold; 
            color: #0d6efd;
            font-size: 1.1em;
        }
        .ingredient-name {
            font-weight: 600;
            color: #212529;
        }
        .aliases {
            font-size: 0.85em;
            color: #6c757d;
            font-style: italic;
            margin-top: 0.25rem;
        }
        .no-results {
            text-align: center;
            padding: 3rem;
            color: #6c757d;
        }
        .stats-row {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1.5rem;
        }
        .copy-btn {
            opacity: 0;
            transition: opacity 0.2s ease;
            border: none;
            background: #f8f9fa;
            color: #6c757d;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
        }
        .density-item:hover .copy-btn {
            opacity: 1;
        }
        .copy-btn:hover {
            background: #e9ecef;
            color: #495057;
        }
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="reference-container">
            <div class="search-container">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h2 class="mb-0">
                        <i class="fas fa-balance-scale text-primary"></i> 
                        Ingredient Density Reference
                    </h2>
                    <small class="text-muted">{{ density_data.common_densities|length }} ingredients</small>
                </div>
                
                <div class="input-group">
                    <span class="input-group-text">
                        <i class="fas fa-search"></i>
                    </span>
                    <input 
                        type="text" 
                        id="searchInput" 
                        class="form-control search-input" 
                        placeholder="Search ingredients by name, alias, or category..."
                        autocomplete="off"
                    >
                    <button class="btn btn-outline-secondary" type="button" id="clearSearch">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="stats-row mt-3">
                    <div class="row text-center">
                        <div class="col">
                            <strong id="totalCount">{{ density_data.common_densities|length }}</strong>
                            <div class="small text-muted">Total Ingredients</div>
                        </div>
                        <div class="col">
                            <strong id="visibleCount">{{ density_data.common_densities|length }}</strong>
                            <div class="small text-muted">Visible</div>
                        </div>
                        <div class="col">
                            <strong>{{ categories|length }}</strong>
                            <div class="small text-muted">Categories</div>
                        </div>
                    </div>
                </div>
                
                <div class="alert alert-info mb-0">
                    <i class="fas fa-info-circle"></i>
                    <strong>How to use:</strong> Search for your ingredient and click the density value to copy it. 
                    Densities are in grams per milliliter (g/ml). If your ingredient isn't listed, 
                    try searching for similar ingredients in the same category.
                </div>
            </div>

            <div id="resultsContainer">
                {% for category_name, items in categories.items() %}
                <div class="category-section" data-category="{{ category_name }}">
                    <h4 class="category-header">
                        {{ category_name }} 
                        <span class="badge bg-light text-dark ms-2">{{ items|length }}</span>
                    </h4>
                    <div class="category-content">
                        <div class="row">
                            {% for item in items %}
                            <div class="col-md-6 col-lg-4 ingredient-item" 
                                 data-name="{{ item.name|lower }}"
                                 data-aliases="{{ (item.aliases or [])|join(' ')|lower }}"
                                 data-category="{{ category_name|lower }}">
                                <div class="density-item">
                                    <div class="d-flex justify-content-between align-items-start">
                                        <div class="flex-grow-1">
                                            <div class="ingredient-name">{{ item.name }}</div>
                                            {% if item.aliases %}
                                            <div class="aliases">{{ item.aliases|join(', ') }}</div>
                                            {% endif %}
                                        </div>
                                        <div class="d-flex align-items-center gap-2">
                                            <span class="density-value">{{ item.density_g_per_ml }}</span>
                                            <button class="copy-btn" onclick="copyDensity('{{ item.density_g_per_ml }}', '{{ item.name }}')">
                                                <i class="fas fa-copy"></i>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <div id="noResults" class="no-results" style="display: none;">
                <i class="fas fa-search-minus fa-3x mb-3"></i>
                <h4>No ingredients found</h4>
                <p>Try adjusting your search terms or browse by category.</p>
            </div>
        </div>
    </div>

    <script>
        const searchInput = document.getElementById('searchInput');
        const clearButton = document.getElementById('clearSearch');
        const resultsContainer = document.getElementById('resultsContainer');
        const noResults = document.getElementById('noResults');
        const visibleCount = document.getElementById('visibleCount');
        const totalCount = document.getElementById('totalCount');
        
        let allItems = document.querySelectorAll('.ingredient-item');
        let allCategories = document.querySelectorAll('.category-section');
        
        function performSearch() {
            const query = searchInput.value.toLowerCase().trim();
            let visibleItems = 0;
            let visibleCategories = 0;
            
            if (!query) {
                // Show all items and categories
                allItems.forEach(item => {
                    item.style.display = '';
                    visibleItems++;
                });
                allCategories.forEach(category => {
                    category.style.display = '';
                    visibleCategories++;
                });
            } else {
                // Filter items
                allItems.forEach(item => {
                    const name = item.dataset.name;
                    const aliases = item.dataset.aliases;
                    const category = item.dataset.category;
                    
                    const matches = name.includes(query) || 
                                  aliases.includes(query) || 
                                  category.includes(query);
                    
                    if (matches) {
                        item.style.display = '';
                        visibleItems++;
                    } else {
                        item.style.display = 'none';
                    }
                });
                
                // Show/hide categories based on visible items
                allCategories.forEach(category => {
                    const visibleInCategory = category.querySelectorAll('.ingredient-item[style=""], .ingredient-item:not([style])').length;
                    if (visibleInCategory > 0) {
                        category.style.display = '';
                        visibleCategories++;
                    } else {
                        category.style.display = 'none';
                    }
                });
            }
            
            // Update counts
            visibleCount.textContent = visibleItems;
            
            // Show/hide no results message
            if (visibleItems === 0) {
                resultsContainer.style.display = 'none';
                noResults.style.display = 'block';
            } else {
                resultsContainer.style.display = 'block';
                noResults.style.display = 'none';
            }
        }
        
        // Search as user types
        searchInput.addEventListener('input', performSearch);
        
        // Clear search
        clearButton.addEventListener('click', () => {
            searchInput.value = '';
            performSearch();
            searchInput.focus();
        });
        
        // Copy density value
        function copyDensity(density, name) {
            navigator.clipboard.writeText(density).then(() => {
                // Show toast notification
                showToast(`Copied ${density} g/ml for ${name}!`);
            }).catch(err => {
                console.error('Failed to copy:', err);
                // Fallback: select text
                const textArea = document.createElement('textarea');
                textArea.value = density;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                showToast(`Copied ${density} g/ml for ${name}!`);
            });
        }
        
        function showToast(message) {
            // Create toast element
            const toast = document.createElement('div');
            toast.className = 'position-fixed top-0 end-0 m-3 alert alert-success alert-dismissible fade show';
            toast.style.zIndex = '9999';
            toast.innerHTML = `
                <i class="fas fa-check-circle me-2"></i>${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            
            document.body.appendChild(toast);
            
            // Auto remove after 3 seconds
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.remove();
                }
            }, 3000);
        }
        
        // Focus search on page load
        searchInput.focus();
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
                searchInput.select();
            }
            if (e.key === 'Escape' && document.activeElement === searchInput) {
                clearButton.click();
            }
        });
    </script>
</body>
</html>
        """

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

        return render_template_string(html_template, categories=categories, density_data=density_data)

    except Exception as e:
        return jsonify({'error': f'Failed to load density reference: {str(e)}'}), 500
