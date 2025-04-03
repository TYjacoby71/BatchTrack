
from unit_converter import UnitConversionService

converter = UnitConversionService()

# Test 1: cup to g with tallow
tallow_result = converter.convert(1, "cup", "g", "tallow")
print(f"1 cup to g (tallow): {tallow_result}g")  # Should succeed

# Test 2: g to cup with beeswax
beeswax_result = converter.convert(200, "g", "cup", "beeswax")
print(f"200g to cup (beeswax): {beeswax_result} cups")  # Should succeed

# Test 3: liters to oz (testing aliases)
volume_result = converter.convert(1, "liters", "oz", "water")
print(f"1 liter to oz: {volume_result}oz")  # Should succeed

# Test 4: Unknown unit test
unknown_result = converter.convert(1, "scoop", "g", "water")
print(f"1 scoop to g: {unknown_result}")  # Should warn and return None
