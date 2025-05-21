
from stock_check_utils import check_stock_for_recipe

def test_check_stock_empty_recipe():
    class DummyRecipe:
        recipe_ingredients = []
    results, ok = check_stock_for_recipe(DummyRecipe())
    assert results == []
    assert ok is True
