import json


def test_public_tools_draft_and_prefill(app, client):
    # Post a simple tool draft (anon)
    payload = {
        "name": "Draft Soap",
        "predicted_yield": 100,
        "predicted_yield_unit": "gram",
        "category_name": "Soaps",
        "ingredients": [{"name": "Olive Oil", "quantity": 10, "unit": "gram"}],
        "consumables": [],
        "containers": [],
    }
    r = client.post(
        "/tools/draft", data=json.dumps(payload), content_type="application/json"
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("success") is True

    # Attempt to load /recipes/new to prefill (will redirect to login since unauthenticated)
    page = client.get("/recipes/new")
    assert page.status_code in (200, 302)


def test_exports_tool_and_recipe_csv_pdf(app, client, db_session):
    # Tool exports should be accessible without auth
    csv_tool = client.get("/exports/tool/soaps/inci.csv")
    assert csv_tool.status_code == 200
    assert csv_tool.mimetype == "text/csv"

    pdf_tool = client.get("/exports/tool/soaps/inci.pdf")
    assert pdf_tool.status_code == 200
    assert pdf_tool.mimetype == "application/pdf"

    # Recipe exports require auth; expect 302 to login when unauthenticated
    resp_recipe = client.get("/exports/recipe/1/soap-inci.csv")
    assert resp_recipe.status_code in (302, 401)
