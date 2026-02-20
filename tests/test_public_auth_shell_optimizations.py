import re


def test_login_page_uses_lightweight_public_shell_without_heavy_app_assets(app):
    client = app.test_client()
    response = client.get("/auth/login")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "jquery-3.6.0.min.js" not in html
    assert "select2.min.js" not in html
    assert "js/core/SessionGuard.js" not in html
    assert "css/filter_panels" not in html
    assert "font-awesome/5.15.4/css/all.min.css" not in html
    assert "FIRST_LANDING_STORAGE_KEY" not in html
    assert "page_context_viewed" not in html
    assert "opacity-75" not in html
    assert "bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js" in html


def test_login_page_start_free_trial_links_share_same_destination(app):
    client = app.test_client()
    response = client.get("/auth/login")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    trial_links = re.findall(
        r'href="(/auth/signup\?source=[^"]+)"[^>]*>\s*Start Free Trial\s*<',
        html,
    )
    assert len(trial_links) >= 2
    assert len(set(trial_links)) == 1
    assert "source=login_start_free_trial" in trial_links[0]


def test_quick_signup_page_disables_analytics_and_fontawesome_payloads(app):
    client = app.test_client()
    response = client.get("/auth/quick-signup")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert "jquery-3.6.0.min.js" not in html
    assert "select2.min.js" not in html
    assert "js/core/SessionGuard.js" not in html
    assert "css/filter_panels" not in html
    assert "font-awesome/5.15.4/css/all.min.css" not in html
    assert "FIRST_LANDING_STORAGE_KEY" not in html
    assert "page_context_viewed" not in html
    assert "bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js" in html


def test_password_recovery_pages_disable_noncritical_public_payloads(app):
    client = app.test_client()
    app.config["AUTH_EMAIL_VERIFICATION_MODE"] = "prompt"
    app.config["AUTH_EMAIL_REQUIRE_PROVIDER"] = False
    for route in ("/auth/forgot-password", "/auth/resend-verification"):
        response = client.get(route)
        assert response.status_code == 200
        html = response.get_data(as_text=True)

        assert "jquery-3.6.0.min.js" not in html
        assert "select2.min.js" not in html
        assert "js/core/SessionGuard.js" not in html
        assert "css/filter_panels" not in html
        assert "font-awesome/5.15.4/css/all.min.css" not in html
        assert "FIRST_LANDING_STORAGE_KEY" not in html
        assert "page_context_viewed" not in html
        assert "bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js" in html
