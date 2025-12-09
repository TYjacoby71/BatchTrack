import pytest


def _assert_public_get(client, path: str, *, label: str, **kwargs):
    """Helper to ensure a GET stays public and does not bounce to login."""
    response = client.get(path, follow_redirects=False, **kwargs)
    assert response.status_code == 200, f"{label} should be public (got {response.status_code})"
    location = response.headers.get("Location", "")
    assert "/auth/login" not in location, f"{label} unexpectedly redirected to login"
    return response


@pytest.mark.usefixtures("app")
def test_public_tools_pages_are_accessible(app):
    """Anonymous visitors should reach the tools landing and calculators without auth."""
    client = app.test_client()
    public_paths = [
        ("/tools/", "tools index"),
        ("/tools/soap", "soap calculator"),
        ("/tools/candles", "candle calculator"),
        ("/tools/lotions", "lotions calculator"),
        ("/tools/herbal", "herbal calculator"),
        ("/tools/baker", "baker calculator"),
    ]

    for path, label in public_paths:
        _assert_public_get(client, path, label=label)


@pytest.mark.usefixtures("app")
def test_anonymous_workflow_can_browse_public_site(app):
    """
    Simulate a public visitor navigating marketing pages so we detect regressions
    that accidentally require authentication (e.g., hitting authorize spots).
    """
    client = app.test_client()

    _assert_public_get(client, "/", label="homepage")
    _assert_public_get(client, "/tools/", label="tools landing")
    _assert_public_get(
        client,
        "/global-items",
        label="global items directory",
        query_string={"type": "ingredient"},
    )
    _assert_public_get(client, "/recipes/library", label="recipe library")
    _assert_public_get(client, "/help/how-it-works", label="how it works")
    _assert_public_get(client, "/auth/signup", label="signup page")
