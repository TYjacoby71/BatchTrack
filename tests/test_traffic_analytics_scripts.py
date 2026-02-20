"""Template-level traffic analytics script injection tests."""


def _render_login_page(client):
    response = client.get("/auth/login")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_layout_omits_analytics_scripts_when_unconfigured(app, client):
    html = _render_login_page(client)
    assert "googletagmanager.com/gtag/js" not in html
    assert "posthog.init(" not in html


def test_login_page_omits_google_analytics_when_measurement_id_present(app, client):
    app.config["GOOGLE_ANALYTICS_MEASUREMENT_ID"] = "G-TEST123456"

    html = _render_login_page(client)

    assert "https://www.googletagmanager.com/gtag/js?id=G-TEST123456" not in html
    assert "gtag('config', \"G-TEST123456\"" not in html


def test_login_page_omits_posthog_when_api_key_present(app, client):
    app.config["POSTHOG_PROJECT_API_KEY"] = "phc_test_key"
    app.config["POSTHOG_HOST"] = "https://us.i.posthog.com"
    app.config["POSTHOG_CAPTURE_PAGEVIEW"] = False
    app.config["POSTHOG_CAPTURE_PAGELEAVE"] = False

    html = _render_login_page(client)

    assert "posthog.init(\"phc_test_key\"" not in html
    assert "api_host: \"https://us.i.posthog.com\"" not in html
    assert "capture_pageview: false" not in html
    assert "capture_pageleave: false" not in html
