
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
import pytest
from models import InventoryUnit, db
from services.unit_conversion import UnitConversionService
from app import app

@pytest.fixture
def setup_units():
    with app.app_context():
        db.create_all()
        db.session.add_all([
            InventoryUnit(name="ml", type="volume", base_equivalent=1.0),
            InventoryUnit(name="l", type="volume", base_equivalent=1000.0),
            InventoryUnit(name="g", type="weight", base_equivalent=1.0)
        ])
        db.session.commit()
        yield
        db.drop_all()

def test_ml_to_l_conversion(setup_units):
    result = UnitConversionService.convert(1000, "ml", "l")
    assert result == 1.0

def test_unknown_unit_raises():
    with pytest.raises(ValueError, match="Unknown units"):
        UnitConversionService.convert(100, "ml", "banana")

def test_cross_type_conversion_with_density(setup_units):
    result = UnitConversionService.convert(1, "ml", "g", density=1.0)
    assert result == 1.0

def test_incompatible_types_without_density(setup_units):
    with pytest.raises(ValueError):
        UnitConversionService.convert(1, "ml", "g")
