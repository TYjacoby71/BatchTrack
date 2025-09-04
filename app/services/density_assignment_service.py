
import json
import os
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher
from flask import current_app
from ..models import InventoryItem, IngredientCategory
from ..extensions import db

class DensityAssignmentService:
    """Service for automatically assigning densities based on reference guide"""
    
    @staticmethod
    def _load_reference_data() -> Dict:
        """Load density reference data from JSON file"""
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            density_file_path = os.path.join(project_root, 'data', 'density_reference.json')
            
            if not os.path.exists(density_file_path):
                current_app.logger.warning(f"Density reference file not found at {density_file_path}")
                return {'common_densities': []}
                
            with open(density_file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            current_app.logger.error(f"Failed to load density reference: {str(e)}")
            return {'common_densities': []}
    
    @staticmethod
    def _similarity_score(name1: str, name2: str) -> float:
        """Calculate similarity between two ingredient names"""
        return SequenceMatcher(None, name1.lower().strip(), name2.lower().strip()).ratio()
    
    @staticmethod
    def find_best_match(ingredient_name: str, threshold: float = 0.8) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Find the best matching reference item or category for an ingredient name
        Returns: (reference_item, match_type) where match_type is 'exact', 'alias', 'similarity', or None
        """
        if not ingredient_name:
            return None, None
            
        reference_data = DensityAssignmentService._load_reference_data()
        items = reference_data.get('common_densities', [])
        
        ingredient_lower = ingredient_name.lower().strip()
        
        # First: Try exact name match
        for item in items:
            if item['name'].lower() == ingredient_lower:
                return item, 'exact'
        
        # Second: Try alias match
        for item in items:
            for alias in item.get('aliases', []):
                if alias.lower() == ingredient_lower:
                    return item, 'alias'
        
        # Third: Try similarity matching
        best_match = None
        best_score = 0
        
        for item in items:
            # Check main name similarity
            score = DensityAssignmentService._similarity_score(ingredient_name, item['name'])
            if score > best_score and score >= threshold:
                best_score = score
                best_match = item
            
            # Check alias similarities
            for alias in item.get('aliases', []):
                score = DensityAssignmentService._similarity_score(ingredient_name, alias)
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = item
        
        if best_match:
            return best_match, 'similarity'
            
        return None, None
    
    @staticmethod
    def get_category_options(organization_id: int) -> List[Dict]:
        """Get all available density options grouped by category"""
        reference_data = DensityAssignmentService._load_reference_data()
        items = reference_data.get('common_densities', [])
        
        # Group reference items by category
        categories = {}
        for item in items:
            category_name = item.get('category', 'Other')
            if category_name not in categories:
                categories[category_name] = {
                    'name': category_name,
                    'items': [],
                    'default_density': None
                }
            categories[category_name]['items'].append(item)
        
        # Calculate default densities for each category (average of items)
        for category_name, category_data in categories.items():
            densities = [item['density_g_per_ml'] for item in category_data['items']]
            category_data['default_density'] = sum(densities) / len(densities)
        
        # Sort items within each category
        for category_data in categories.values():
            category_data['items'].sort(key=lambda x: x['name'])
        
        return list(categories.values())
    
    @staticmethod
    def assign_density_to_ingredient(ingredient: InventoryItem, reference_item_name: str = None, 
                                   use_category_default: bool = False, category_name: str = None) -> bool:
        """
        Assign density to an ingredient based on reference guide
        Returns True if density was assigned, False otherwise
        """
        try:
            if reference_item_name:
                # Find specific reference item
                reference_data = DensityAssignmentService._load_reference_data()
                items = reference_data.get('common_densities', [])
                
                for item in items:
                    if item['name'] == reference_item_name:
                        ingredient.density = item['density_g_per_ml']
                        ingredient.reference_item_name = reference_item_name
                        ingredient.density_source = 'reference_item'
                        db.session.commit()
                        return True
            
            elif use_category_default and category_name:
                # Use category default density
                categories = DensityAssignmentService.get_category_options(ingredient.organization_id)
                for category in categories:
                    if category['name'] == category_name:
                        ingredient.density = category['default_density']
                        ingredient.reference_item_name = None
                        ingredient.density_source = 'category_default'
                        db.session.commit()
                        return True
            
            return False
            
        except Exception as e:
            current_app.logger.error(f"Failed to assign density: {str(e)}")
            db.session.rollback()
            return False
    
    @staticmethod
    def auto_assign_density_on_creation(ingredient: InventoryItem) -> bool:
        """
        Automatically assign density when creating a new ingredient
        """
        if ingredient.density is not None:
            return True  # Already has density
            
        match_item, match_type = DensityAssignmentService.find_best_match(ingredient.name)
        
        if match_item and match_type in ['exact', 'alias']:
            # High confidence match - auto assign
            ingredient.density = match_item['density_g_per_ml']
            ingredient.reference_item_name = match_item['name']
            ingredient.density_source = 'auto_assigned'
            return True
        elif match_item and match_type == 'similarity':
            # Lower confidence - suggest but don't auto-assign
            current_app.logger.info(f"Similarity match found for '{ingredient.name}': '{match_item['name']}' (density: {match_item['density_g_per_ml']})")
            return False
            
        return False
