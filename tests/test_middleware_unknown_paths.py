from app.utils.cache_manager import app_cache


def test_unknown_unauthenticated_path_returns_404(app):
    client = app.test_client()

    response = client.get("/ssl.key", follow_redirects=False)

    assert response.status_code == 404
    assert "/auth/login" not in (response.headers.get("Location") or "")
    assert response.get_data(as_text=True) == "Not Found"


def test_unknown_api_path_returns_json_404(app):
    client = app.test_client()

    response = client.get(
        "/api/not-a-real-endpoint",
        headers={"Accept": "application/json"},
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "Not found"


def test_known_protected_route_still_redirects_to_login(app):
    client = app.test_client()

    response = client.get("/dashboard", follow_redirects=False)

    assert response.status_code in {302, 303}
    location = response.headers.get("Location") or ""
    assert "/auth/login" in location
    assert "next=" in location


def test_marketing_context_skips_expensive_work_for_login(app, monkeypatch):
    client = app.test_client()
    from app import template_context

    def _fail_if_called(*_args, **_kwargs):
        raise AssertionError("read_json_file should not be called for /auth/login")

    monkeypatch.setattr(template_context, "read_json_file", _fail_if_called)

    response = client.get("/auth/login", follow_redirects=False)

    assert response.status_code == 200


def test_marketing_context_still_runs_for_homepage(app, monkeypatch):
    client = app.test_client()
    from app import template_context

    calls = []

    def _record_calls(_path, default=None):
        calls.append(str(_path))
        return default if default is not None else []

    monkeypatch.setattr(template_context, "read_json_file", _record_calls)
    app_cache.clear_prefix("marketing:")

    response = client.get("/", query_string={"refresh": "1"}, follow_redirects=False)

    assert response.status_code == 200
    assert calls
