
from datetime import datetime
from flask_login import current_user
from ..models import Unit, CustomUnitMapping, InventoryItem as Ingredient, ConversionLog
from ..extensions import db

class ConversionEngine:
    """
    Enhanced unit conversion engine with custom mappings and density support
    """
    
    # Base conversion factors to grams and milliliters
    WEIGHT_CONVERSIONS = {
        'g': 1.0,
        'kg': 1000.0,
        'oz': 28.3495,
        'lb': 453.592,
        'lbs': 453.592,
        'pound': 453.592,
        'pounds': 453.592
    }
    
    VOLUME_CONVERSIONS = {
        'ml': 1.0,
        'l': 1000.0,
        'liter': 1000.0,
        'liters': 1000.0,
        'fl oz': 29.5735,
        'fl_oz': 29.5735,
        'cup': 236.588,
        'cups': 236.588,
        'tbsp': 14.7868,
        'tsp': 4.92892,
        'pint': 473.176,
        'pints': 473.176,
        'quart': 946.353,
        'quarts': 946.353,
        'gallon': 3785.41,
        'gallons': 3785.41
    }
    
    # Common density values (g/ml)
    DENSITY_DATABASE = {
        'water': 1.0,
        'honey': 1.4,
        'oil': 0.92,
        'milk': 1.03,
        'cream': 1.01,
        'butter': 0.91,
        'flour': 0.55,
        'sugar': 0.85,
        'salt': 2.16
    }

    @classmethod
    def convert_units(cls, amount, from_unit, to_unit, ingredient_id=None, density=None):
        """
        Convert between units with support for custom mappings and density
        """
        if from_unit == to_unit:
            return amount

        # Check for custom mapping first
        custom_conversion = cls._get_custom_conversion(from_unit, to_unit, ingredient_id)
        if custom_conversion:
            result = amount * custom_conversion
            cls._log_conversion(amount, from_unit, to_unit, result, 'custom_mapping', ingredient_id)
            return result

        # Try standard conversions
        try:
            result = cls._standard_conversion(amount, from_unit, to_unit, ingredient_id, density)
            cls._log_conversion(amount, from_unit, to_unit, result, 'standard', ingredient_id)
            return result
        except ValueError as e:
            cls._log_conversion(amount, from_unit, to_unit, None, 'failed', ingredient_id, str(e))
            raise e

    @classmethod
    def _get_custom_conversion(cls, from_unit, to_unit, ingredient_id):
        """Get custom conversion factor if exists"""
        if not ingredient_id:
            return None
            
        mapping = CustomUnitMapping.query.filter_by(
            ingredient_id=ingredient_id,
            from_unit=from_unit,
            to_unit=to_unit
        ).first()
        
        return mapping.conversion_factor if mapping else None

    @classmethod
    def _standard_conversion(cls, amount, from_unit, to_unit, ingredient_id=None, density=None):
        """Perform standard unit conversions"""
        
        # Same unit family conversions
        if from_unit in cls.WEIGHT_CONVERSIONS and to_unit in cls.WEIGHT_CONVERSIONS:
            return cls._convert_within_family(amount, from_unit, to_unit, cls.WEIGHT_CONVERSIONS)
        
        if from_unit in cls.VOLUME_CONVERSIONS and to_unit in cls.VOLUME_CONVERSIONS:
            return cls._convert_within_family(amount, from_unit, to_unit, cls.VOLUME_CONVERSIONS)
        
        # Cross-family conversions (weight ↔ volume)
        if ((from_unit in cls.WEIGHT_CONVERSIONS and to_unit in cls.VOLUME_CONVERSIONS) or
            (from_unit in cls.VOLUME_CONVERSIONS and to_unit in cls.WEIGHT_CONVERSIONS)):
            return cls._convert_weight_volume(amount, from_unit, to_unit, ingredient_id, density)
        
        # Count conversions
        if from_unit == 'count' or to_unit == 'count':
            return cls._convert_count(amount, from_unit, to_unit, ingredient_id)
        
        raise ValueError(f"Cannot convert from {from_unit} to {to_unit}")

    @classmethod
    def _convert_within_family(cls, amount, from_unit, to_unit, conversion_table):
        """Convert within the same unit family"""
        from_factor = conversion_table[from_unit]
        to_factor = conversion_table[to_unit]
        return amount * (from_factor / to_factor)

    @classmethod
    def _convert_weight_volume(cls, amount, from_unit, to_unit, ingredient_id=None, density=None):
        """Convert between weight and volume using density"""
        
        # Get density
        actual_density = density or cls._get_ingredient_density(ingredient_id)
        if not actual_density:
            raise ValueError("Cannot convert between weight and volume without density")
        
        # Convert to base units first
        if from_unit in cls.WEIGHT_CONVERSIONS:
            # Weight to volume: weight(g) / density(g/ml) = volume(ml)
            weight_in_grams = amount * cls.WEIGHT_CONVERSIONS[from_unit]
            volume_in_ml = weight_in_grams / actual_density
            return volume_in_ml / cls.VOLUME_CONVERSIONS[to_unit]
        else:
            # Volume to weight: volume(ml) * density(g/ml) = weight(g)
            volume_in_ml = amount * cls.VOLUME_CONVERSIONS[from_unit]
            weight_in_grams = volume_in_ml * actual_density
            return weight_in_grams / cls.WEIGHT_CONVERSIONS[to_unit]

    @classmethod
    def _convert_count(cls, amount, from_unit, to_unit, ingredient_id=None):
        """Handle count conversions"""
        if not ingredient_id:
            raise ValueError("Cannot convert to/from count without ingredient reference")
        
        ingredient = Ingredient.query.get(ingredient_id)
        if not ingredient:
            raise ValueError(f"Ingredient {ingredient_id} not found")
        
        if from_unit == 'count':
            # Count to other unit
            if not ingredient.unit_weight:
                raise ValueError(f"No unit weight defined for {ingredient.name}")
            
            total_weight = amount * ingredient.unit_weight
            if to_unit in cls.WEIGHT_CONVERSIONS:
                return total_weight / cls.WEIGHT_CONVERSIONS[to_unit]
            elif to_unit in cls.VOLUME_CONVERSIONS:
                density = cls._get_ingredient_density(ingredient_id)
                if not density:
                    raise ValueError("Cannot convert count to volume without density")
                volume_ml = total_weight / density
                return volume_ml / cls.VOLUME_CONVERSIONS[to_unit]
        else:
            # Other unit to count
            if not ingredient.unit_weight:
                raise ValueError(f"No unit weight defined for {ingredient.name}")
            
            if from_unit in cls.WEIGHT_CONVERSIONS:
                total_weight = amount * cls.WEIGHT_CONVERSIONS[from_unit]
            elif from_unit in cls.VOLUME_CONVERSIONS:
                density = cls._get_ingredient_density(ingredient_id)
                if not density:
                    raise ValueError("Cannot convert volume to count without density")
                volume_ml = amount * cls.VOLUME_CONVERSIONS[from_unit]
                total_weight = volume_ml * density
            else:
                raise ValueError(f"Cannot convert {from_unit} to count")
            
            return total_weight / ingredient.unit_weight

    @classmethod
    def _get_ingredient_density(cls, ingredient_id):
        """Get density for an ingredient"""
        if not ingredient_id:
            return None
            
        ingredient = Ingredient.query.get(ingredient_id)
        if not ingredient:
            return None
        
        # Check if ingredient has custom density
        if ingredient.density:
            return ingredient.density
        
        # Check density database by name
        ingredient_name = ingredient.name.lower()
        for key, density in cls.DENSITY_DATABASE.items():
            if key in ingredient_name:
                return density
        
        return None

    @classmethod
    def _log_conversion(cls, amount, from_unit, to_unit, result, method, ingredient_id=None, error=None):
        """Log conversion for audit trail"""
        try:
            log = ConversionLog(
                amount=amount,
                from_unit=from_unit,
                to_unit=to_unit,
                result=result,
                method=method,
                ingredient_id=ingredient_id,
                error_message=error,
                user_id=current_user.id if current_user.is_authenticated else None,
                timestamp=datetime.utcnow()
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            # Don't let logging errors break conversions
            pass

    @classmethod
    def get_supported_units(cls):
        """Get all supported units"""
        standard_units = list(cls.WEIGHT_CONVERSIONS.keys()) + list(cls.VOLUME_CONVERSIONS.keys()) + ['count']
        custom_units = [unit.name for unit in Unit.query.all()]
        return list(set(standard_units + custom_units))

    @classmethod
    def can_convert(cls, from_unit, to_unit, ingredient_id=None):
        """Check if conversion is possible"""
        if from_unit == to_unit:
            return True
        
        # Check custom mapping
        if cls._get_custom_conversion(from_unit, to_unit, ingredient_id):
            return True
        
        # Check standard conversions
        try:
            cls._standard_conversion(1.0, from_unit, to_unit, ingredient_id)
            return True
        except ValueError:
            return False


# Legacy alias for backward compatibility
UnitConversionService = ConversionEngine
