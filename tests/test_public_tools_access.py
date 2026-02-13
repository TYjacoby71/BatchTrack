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
    assert 'id="stageWaterOutput"' in html


@pytest.mark.usefixtures("app")
def test_public_soap_calculation_api_is_accessible(app):
    """Anonymous users should be able to run soap calculations via tool API."""
    client = app.test_client()
    payload = {
        "oils": [{"grams": 650, "sap_koh": 190}],
        "lye": {"selected": "NaOH", "superfat": 5, "purity": 100},
        "water": {"method": "percent", "water_pct": 33},
    }
    response = client.post("/tools/api/soap/calculate", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("success") is True
    result = data.get("result") or {}
    assert result.get("water_g", 0) > 0
    assert result.get("lye_adjusted_g", 0) > 0


@pytest.mark.usefixtures("app")
def test_public_soap_calculation_api_works_with_csrf_enforcement_enabled(app):
    """Public soap compute endpoint should remain available even when CSRF is globally on."""
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    payload = {
        "oils": [{"grams": 650, "sap_koh": 190}],
        "lye": {"selected": "NaOH", "superfat": 5, "purity": 100},
        "water": {"method": "percent", "water_pct": 33},
    }

    response = client.post("/tools/api/soap/calculate", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("success") is True
    result = data.get("result") or {}
    assert result.get("water_g", 0) > 0
    assert result.get("lye_adjusted_g", 0) > 0


@pytest.mark.usefixtures("app")
def test_public_vendor_signup_api_works_with_csrf_enforcement_enabled(app, monkeypatch):
    """Public vendor signup should keep working for anonymous users when CSRF is globally on."""
    app.config["WTF_CSRF_ENABLED"] = True
    monkeypatch.setattr("app.utils.json_store.read_json_file", lambda *_args, **_kwargs: [])
    monkeypatch.setattr("app.utils.json_store.write_json_file", lambda *_args, **_kwargs: None)

    client = app.test_client()
    payload = {
        "item_name": "Olive Oil",
        "item_id": "123",
        "company_name": "Acme Supplies",
        "contact_name": "Jane Doe",
        "email": "jane@example.com",
    }
    response = client.post("/api/vendor-signup", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert data.get("success") is True


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
def test_public_branding_assets_are_accessible(app):
    """Logo and favicon assets should remain publicly available for marketing pages."""
    client = app.test_client()
    brand_asset_paths = [
        "/branding/full-logo.svg",
        "/branding/full-logo-header.svg",
        "/branding/app-tile.svg",
    ]

    for path in brand_asset_paths:
        response = _assert_public_get(client, path, label=f"branding asset {path}")
        assert response.mimetype == "image/svg+xml"
        body = response.get_data(as_text=True)
        assert "<svg" in body


@pytest.mark.usefixtures("app")
def test_public_crawler_assets_are_accessible(app):
    """Crawler assets should be available on root paths."""
    client = app.test_client()

    sitemap_response = _assert_public_get(client, "/sitemap.xml", label="sitemap.xml")
    sitemap_body = sitemap_response.get_data(as_text=True)
    assert sitemap_response.mimetype in {"application/xml", "text/xml"}
    assert "<urlset" in sitemap_body
    assert "https://www.batchtrack.com/" in sitemap_body

    robots_response = _assert_public_get(client, "/robots.txt", label="robots.txt")
    robots_body = robots_response.get_data(as_text=True)
    assert robots_response.mimetype == "text/plain"
    assert "User-agent:" in robots_body
    assert "Sitemap: https://www.batchtrack.com/sitemap.xml" in robots_body

    llms_response = _assert_public_get(client, "/llms.txt", label="llms.txt")
    llms_body = llms_response.get_data(as_text=True)
    assert llms_response.mimetype == "text/plain"
    assert "BatchTrack" in llms_body
    assert "Primary site: https://www.batchtrack.com/" in llms_body


@pytest.mark.usefixtures("app")
def test_legacy_dev_login_path_redirects_to_auth_namespace(app):
    """Legacy /dev-login URL should redirect to the canonical auth route."""
    client = app.test_client()
    response = client.get("/dev-login", follow_redirects=False)
    assert response.status_code in {301, 302}
    assert response.headers.get("Location", "").endswith("/auth/dev-login")


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
