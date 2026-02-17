"""CSRF error handling regression tests."""


def _enable_csrf(app):
    app.config["WTF_CSRF_ENABLED"] = True
    app.config["WTF_CSRF_CHECK_DEFAULT"] = True


def test_csrf_html_post_redirects_to_login_with_flash(app):
    _enable_csrf(app)
    client = app.test_client()

    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "wrong-password"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Your session expired or this form is out of date. Please try again." in body


def test_csrf_json_post_returns_structured_error(app):
    _enable_csrf(app)
    client = app.test_client()

    response = client.post(
        "/auth/login",
        json={"username": "testuser", "password": "wrong-password"},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 400
    assert response.is_json
    payload = response.get_json()
    assert payload["error"] == "csrf_validation_failed"
    assert "Refresh and try again." in payload["message"]


def test_csrf_redirect_ignores_external_referer(app):
    _enable_csrf(app)
    client = app.test_client()

    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "wrong-password"},
        headers={"Referer": "https://attacker.example/fake"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["Location"].endswith("/auth/login")
