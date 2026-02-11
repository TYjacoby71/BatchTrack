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
def test_public_soap_page_uses_marketing_header_without_center_overlay(app):
    """Anonymous soap page should use marketing nav without center-title overlay."""
    client = app.test_client()
    response = _assert_public_get(client, "/tools/soap", label="soap calculator")
    html = response.get_data(as_text=True)

    assert 'id="publicMarketingNav"' in html
    assert '<span class="navbar-text fw-semibold">Soap Formulator</span>' not in html
    assert "position-absolute top-50 start-50 translate-middle text-center" not in html


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
    _assert_public_get(client, "/lp/hormozi", label="landing page (results-first)")
    _assert_public_get(client, "/lp/robbins", label="landing page (transformation-first)")
    _assert_public_get(client, "/auth/signup", label="signup page")


@pytest.mark.usefixtures("app")
def test_staging_homepage_variant_switcher_visibility(app):
    """Homepage variant switcher should only appear in staging."""
    client = app.test_client()

    app.config["ENV"] = "testing"
    app.config["FLASK_ENV"] = "testing"
    testing_response = _assert_public_get(
        client,
        "/",
        label="homepage in non-staging",
        query_string={"refresh": "1"},
    )
    testing_html = testing_response.get_data(as_text=True)
    assert "Home Variants" not in testing_html

    app.config["ENV"] = "staging"
    app.config["FLASK_ENV"] = "staging"
    staging_response = _assert_public_get(
        client,
        "/",
        label="homepage in staging",
        query_string={"refresh": "1"},
    )
    staging_html = staging_response.get_data(as_text=True)
    assert "Home Variants" in staging_html
    assert "/lp/hormozi" in staging_html
    assert "/lp/robbins" in staging_html
