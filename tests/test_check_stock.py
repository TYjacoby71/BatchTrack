
import pytest
from app import app, db
from models import Recipe
from services.stock_check import universal_stock_check

def test_check_stock_empty_recipe():
    with app.app_context():
        class DummyRecipe:
            recipe_ingredients = []
        
        result = universal_stock_check(DummyRecipe())
        assert result['stock_check'] == []
        assert result['all_ok'] is True
