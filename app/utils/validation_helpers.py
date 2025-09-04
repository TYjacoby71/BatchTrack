
def validate_density(density_value):
    """
    Validate density value - must be positive and realistic
    Returns validated density or None if invalid
    """
    if density_value is None:
        return None
    
    try:
        density = float(density_value)
        # Density must be positive and realistic (between 0.01 and 10.0 g/ml)
        if 0.01 <= density <= 10.0:
            return density
        else:
            return None
    except (ValueError, TypeError):
        return None

def get_density_description(density):
    """Get human-readable description of density"""
    if density is None:
        return "No density set"
    elif density < 0.5:
        return f"{density} g/ml (Very light - oils/alcohols)"
    elif density < 0.9:
        return f"{density} g/ml (Light - most oils)"
    elif density < 1.1:
        return f"{density} g/ml (Water-like)"
    elif density < 1.5:
        return f"{density} g/ml (Heavy liquids - syrups)"
    else:
        return f"{density} g/ml (Very heavy - clay/minerals)"
