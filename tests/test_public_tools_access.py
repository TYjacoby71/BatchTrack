import pytest


@pytest.mark.usefixtures("app")
def test_public_tools_pages_are_accessible(app):
    """Anonymous visitors should reach the tools landing and calculators without auth."""
    client = app.test_client()
    public_paths = [
        "/tools/",
        "/tools/soap",
        "/tools/candles",
        "/tools/lotions",
        "/tools/herbal",
        "/tools/baker",
    ]

    for path in public_paths:
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 200, f"{path} should be public, got {resp.status_code}"
