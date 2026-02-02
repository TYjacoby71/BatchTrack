import pytest


@pytest.mark.usefixtures("app")
def test_public_soapcalc_oils_search_returns_grouped_results(app):
    client = app.test_client()
    response = client.get(
        "/api/public/soapcalc-items/search",
        query_string={"q": "coconut", "group": "ingredient"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["results"], "Expected soapcalc search results"
    group = payload["results"][0]
    assert "forms" in group
    assert group["forms"], "Expected grouped forms for soapcalc oils"
    form = group["forms"][0]
    assert "saponification_value" in form
    assert "iodine_value" in form
    assert "fatty_acid_profile" in form
    assert "ingredient_category_name" in form
    assert "default_unit" in form
