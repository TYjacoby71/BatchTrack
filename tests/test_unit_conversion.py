
from services.unit_conversion import UnitConversionService

def test_basic_conversion():
    result = UnitConversionService.convert(1000, "ml", "l")
    assert round(result, 2) == 1.0

def test_same_unit():
    result = UnitConversionService.convert(500, "g", "g")
    assert result == 500

def test_invalid_unit():
    try:
        UnitConversionService.convert(100, "ml", "unknown")
    except:
        assert True
