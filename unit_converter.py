class UnitConversionService:
    UNIT_ALIASES = {
        "cups": "cup", "tbsps": "tbsp", "tsps": "tsp",
        "liters": "liter", "gallons": "gallon",
        "lbs": "lb", "kgs": "kg", "ozs": "oz",
        "milliliters": "ml", "grams": "g",
    }

    VOLUME_TO_ML = {
        "ml": 1,
        "liter": 1000,
        "l": 1000,
        "tsp": 4.92892,
        "tbsp": 14.7868,
        "cup": 236.588,
        "pint": 473.176,
        "quart": 946.353,
        "gallon": 3785.41,
    }

    WEIGHT_TO_G = {
        "mg": 0.001,
        "g": 1,
        "kg": 1000,
        "oz": 28.3495,
        "lb": 453.592,
    }

    DENSITIES = {
        "water": 1.0,
        "milk": 1.03,
        "olive oil": 0.91,
        "tallow": 0.92,
        "beeswax": 0.96
    }

    def convert_volume(self, amount, from_unit, to_unit):
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()
        from_unit = self.UNIT_ALIASES.get(from_unit, from_unit)
        to_unit = self.UNIT_ALIASES.get(to_unit, to_unit)
        if from_unit not in self.VOLUME_TO_ML or to_unit not in self.VOLUME_TO_ML:
            return None
        ml = amount * self.VOLUME_TO_ML[from_unit]
        return ml / self.VOLUME_TO_ML[to_unit]

    def convert_weight(self, amount, from_unit, to_unit):
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()
        from_unit = self.UNIT_ALIASES.get(from_unit, from_unit)
        to_unit = self.UNIT_ALIASES.get(to_unit, to_unit)
        if from_unit not in self.WEIGHT_TO_G or to_unit not in self.WEIGHT_TO_G:
            return None
        g = amount * self.WEIGHT_TO_G[from_unit]
        return g / self.WEIGHT_TO_G[to_unit]

    def convert_between_types(self, amount, from_unit, to_unit, material="water"):
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()
        from_unit = self.UNIT_ALIASES.get(from_unit, from_unit)
        to_unit = self.UNIT_ALIASES.get(to_unit, to_unit)
        if material not in self.DENSITIES:
            return None
        if from_unit in self.VOLUME_TO_ML and to_unit in self.WEIGHT_TO_G:
            ml = amount * self.VOLUME_TO_ML[from_unit]
            g = ml * self.DENSITIES[material]
            return g / self.WEIGHT_TO_G[to_unit]
        if from_unit in self.WEIGHT_TO_G and to_unit in self.VOLUME_TO_ML:
            g = amount * self.WEIGHT_TO_G[from_unit]
            ml = g / self.DENSITIES[material]
            return ml / self.VOLUME_TO_ML[to_unit]
        return None

    def convert(self, amount, from_unit, to_unit, material="water"):
        if from_unit in self.VOLUME_TO_ML and to_unit in self.VOLUME_TO_ML:
            return self.convert_volume(amount, from_unit, to_unit)
        elif from_unit in self.WEIGHT_TO_G and to_unit in self.WEIGHT_TO_G:
            return self.convert_weight(amount, from_unit, to_unit)
        return self.convert_between_types(amount, from_unit, to_unit, material)

    def convert_units(self, value, from_unit, to_unit):
        """Convert value between units"""
        try:
            return self.convert(float(value), from_unit, to_unit)
        except (ValueError, TypeError):
            return None

    def parse_unit(self, unit_str):
        """Parse a unit string into a standardized format"""
        return unit_str.lower().strip() if unit_str else ""


converter = UnitConversionService()

def can_fulfill(stock_qty, stock_unit, needed_qty, needed_unit):
    try:
        stock_qty = float(stock_qty)
        needed_qty = float(needed_qty)
        converted_needed = converter.convert(needed_qty, needed_unit, stock_unit)
        if converted_needed is None:
            return False
        return stock_qty >= converted_needed
    except:
        return False

def format_unit_value(value, unit):
    """Format a value with its unit for display"""
    if value is None or value == '':
        return "N/A"
    try:
        value = float(value)
        unit = unit.strip() if unit else ''
        return f"{value:.2f}{' ' + unit if unit else ''}"
    except (ValueError, TypeError):
        return f"{value}{' ' + unit if unit else ''}"

def check_stock_availability(recipe_qty, recipe_unit, stock_qty, stock_unit):
    """
    Check if there's enough stock for a recipe
    Returns: (bool available, float converted_stock_qty, float needed_qty)
    """
    try:
        if not recipe_qty or not stock_qty or not recipe_unit or not stock_unit:
            return False, 0, 0

        recipe_qty = float(recipe_qty) if recipe_qty else 0
        stock_qty = float(stock_qty) if stock_qty else 0

        converted_stock = converter.convert(stock_qty, stock_unit, recipe_unit)
        if converted_stock is None:
            return False, 0, recipe_qty

        return converted_stock >= recipe_qty, converted_stock, recipe_qty
    except (ValueError, TypeError):
        return False, 0, 0