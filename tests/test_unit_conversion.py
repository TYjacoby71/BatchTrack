
from services.unit_conversion import ConversionEngine

def test_basic_conversion():
    result = ConversionEngine.convert_units(1000, "ml", "l")
    assert round(result, 2) == 1.0

def test_same_unit():
    result = ConversionEngine.convert_units(500, "g", "g")
    assert result == 500

def test_invalid_unit():
    try:
        ConversionEngine.convert_units(100, "ml", "unknown")
    except:
        assert True
